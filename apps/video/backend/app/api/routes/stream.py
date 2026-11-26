"""Bazzy Video — playback

GET /api/v1/titles/{id}/play           (signed in) → {"hls_url": ...} if the viewer has access
GET /api/v1/stream/{id}/{path}.m3u8?t= → HLS playlist from B2, rewritten:
    child playlists keep pointing back here (with the token),
    segments point at the Bunny CDN (B2_PUBLIC_URL) or at short-lived presigned B2 URLs.
"""
import posixpath
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.models import Title, User, UserRole
from app.services import storage
from app.services.credit_service import CreditService

router = APIRouter(tags=["stream"])


def _is_external(url: str | None) -> bool:
    return bool(url) and url.startswith(("http://", "https://"))


async def _has_access(db: AsyncSession, user: User, title: Title) -> bool:
    if title.is_free or user.role == UserRole.ADMIN:
        return True
    if user.filmmaker_profile and user.filmmaker_profile.id == title.filmmaker_id:
        return True
    return await CreditService().active_access(db, user.id, title.id) is not None


def _stream_token(title_id: str, user_id: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=settings.STREAM_TOKEN_TTL_SECONDS)
    return jwt.encode({"typ": "stream", "tid": title_id, "sub": user_id, "exp": exp},
                      settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def rewrite_playlist(text: str, title_id: str, path: str, token: str) -> str:
    """Child playlists → back through this endpoint (with the token);
    segments → CDN URL or presigned B2 URL (storage.segment_url)."""
    base, here, out = f"titles/{title_id}", posixpath.dirname(path), []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            out.append(line)
            continue
        rel = posixpath.normpath(posixpath.join(here, s))
        if s.endswith(".m3u8"):
            out.append(f"/api/v1/stream/{title_id}/{rel}?t={token}")
        else:
            out.append(storage.segment_url(f"{base}/{rel}"))
    return "\n".join(out) + "\n"


@router.get("/titles/{title_id}/play")
async def play(title_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    title = await db.get(Title, title_id)
    if not title:
        raise HTTPException(404, "Title not found")
    if not await _has_access(db, user, title):
        raise HTTPException(402, "Rent or buy this title to watch it")
    if not title.hls_manifest_url:
        raise HTTPException(409, "This title is still processing")
    if _is_external(title.hls_manifest_url):        # demo titles / legacy CDN URLs
        return {"hls_url": title.hls_manifest_url}
    token = _stream_token(title.id, user.id)
    return {"hls_url": f"/api/v1/stream/{title.id}/master.m3u8?t={token}"}


@router.get("/stream/{title_id}/{path:path}")
async def stream_playlist(title_id: str, path: str, t: str = Query(...)):
    try:
        claims = jwt.decode(t, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(401, "Playback link expired — press play again")
    if claims.get("typ") != "stream" or claims.get("tid") != title_id:
        raise HTTPException(403, "Invalid playback link")

    path = posixpath.normpath(path)
    if path.startswith("..") or path.startswith("/") or not path.endswith(".m3u8"):
        raise HTTPException(400, "Only playlists are served here")

    base = f"titles/{title_id}"
    try:
        text = storage.read_text(f"{base}/{path}")
    except storage.StorageNotConfigured as e:
        raise HTTPException(503, str(e))
    except Exception:
        raise HTTPException(404, "Playlist not found")

    out = rewrite_playlist(text, title_id, path, t)
    return Response(out, media_type="application/vnd.apple.mpegurl",
                    headers={"Cache-Control": "private, no-store"})
