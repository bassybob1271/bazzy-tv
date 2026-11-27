"""Bazzy Live — livestream routes, on the shared Bazzy TV backend.

A show is a Title with a live_state. Tickets go through the same purchase as a film rental, so they
come out of the one Bazzy wallet and pay the artist the same creator share; if the band has a split
sheet for the show (app "live", source_ref = the show's id), the share is divided across everyone on it.

How a show reaches viewers:

  ATEM switcher ──RTMP──▶ MediaMTX ──HLS──▶ hls.js in the browser
   (artist's venue)       (mediamtx container)   (/hls/live/<playback_id>/index.m3u8)

* The artist schedules a show here and gets an RTMP server URL + stream key,
  which go into ATEM Software Control → Output → Live Stream (or they import
  the generated Streaming.xml).
* MediaMTX asks /live/ingest/auth before every publish and every read:
  publishing needs the show's stream key, watching needs a playback pass
  from /live/{id}/playback (only issued to ticket holders).
* MediaMTX calls /live/ingest/hook when the feed starts and stops, which
  flips the show between scheduled → on_air → ended.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qs
from xml.sax.saxutils import escape
import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from jose import jwt, JWTError
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_creator_user, get_current_user
from app.db.database import get_db
from app.models.models import (
    Title, User, ContentCategory, ContentStatus, LiveState, AccessType, FilmmakerProfile,
)
from app.api.routes.titles import TitleOut
from app.services.discovery_service import DiscoveryService
from app.services.credit_service import CreditService

router = APIRouter(prefix="/live", tags=["live"])
credits_svc = CreditService()

PASS_TYPE = "playback"


def new_playback_id() -> str:
    return secrets.token_hex(8)


def new_stream_key() -> str:
    return secrets.token_urlsafe(24)


def ingest_info(t: Title) -> dict:
    """What the artist types into ATEM Software Control."""
    return {
        "server_url": settings.INGEST_RTMP_URL,
        # MediaMTX reads "<path>?key=<secret>": the path is public, the key isn't
        "stream_key": f"{t.playback_id}?key={t.stream_key}",
        "playback_id": t.playback_id,
    }


def _owned_show(t: Optional[Title], user: User) -> Title:
    if not t:
        raise HTTPException(404, "Livestream not found")
    is_admin = user.role == "admin"
    fm = user.filmmaker_profile
    if not is_admin and (not fm or t.filmmaker_id != fm.id):
        raise HTTPException(404, "Livestream not found")
    return t


# ── Artist: schedule + ATEM setup ─────────────────────────────────────────────

async def _artist_profile(db: AsyncSession, user: User) -> FilmmakerProfile:
    """Any member can put on a show. Their first show gives them a creator profile (earnings,
    splits, payouts) without film-upload rights on Bazzy TV."""
    if user.filmmaker_profile:
        return user.filmmaker_profile
    fm = FilmmakerProfile(id=str(uuid.uuid4()), user_id=user.id)
    db.add(fm)
    await db.flush()
    return fm


@router.get("/home-rails")
async def live_home_rails(db: AsyncSession = Depends(get_db)):
    """Bazzy Live's home page: the poster slider (on air first, then soonest) and past shows."""
    rails = await DiscoveryService().get_live_rails(db)
    return {k: [TitleOut.model_validate(t).model_dump() for t in v] for k, v in rails.items()}


class LivestreamCreate(BaseModel):
    title: str
    synopsis: str = ""
    category: ContentCategory = ContentCategory.CONCERTS
    performer_name: Optional[str] = None
    venue: Optional[str] = None
    starts_at: datetime
    rent_credits: int = settings.CREDITS_TICKET_DEFAULT  # ticket
    buy_credits: int = 800                                # keep the replay
    is_free: bool = False
    poster_url: Optional[str] = None


@router.post("/", status_code=201)
async def schedule_livestream(
    req: LivestreamCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.category.name not in ("CONCERTS", "ALBUM_RELEASES", "LISTENING", "SCREENINGS", "SOUND_BATHS"):
        raise HTTPException(400, "Pick a show type: concert, album release, listening, screening or sound bath")
    fm = await _artist_profile(db, current_user)
    base = "".join(c if c.isalnum() else "-" for c in req.title.lower()).strip("-")[:90]
    t = Title(
        id=str(uuid.uuid4()),
        filmmaker_id=fm.id if fm else None,
        title=req.title,
        slug=f"{base}-{uuid.uuid4().hex[:6]}",
        synopsis=req.synopsis,
        category=req.category,
        performer_name=req.performer_name or current_user.display_name,
        venue=req.venue,
        starts_at=req.starts_at,
        year=req.starts_at.year,
        rent_credits=0 if req.is_free else req.rent_credits,
        buy_credits=0 if req.is_free else req.buy_credits,
        is_free=req.is_free,
        poster_url=req.poster_url,
        drm_enabled=False,
        live_state=LiveState.SCHEDULED,
        playback_id=new_playback_id(),
        stream_key=new_stream_key(),
        # Listed once an admin approves it, same as Bazzy Video uploads
        status=ContentStatus.REVIEW,
    )
    db.add(t)
    await db.commit()
    # title_id is also the show id for its split sheet (Splits → a live show → this id).
    return {"title_id": t.id, "slug": t.slug, "status": "review", "ingest": ingest_info(t)}


@router.get("/mine")
async def my_livestreams(
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    fm = current_user.filmmaker_profile
    if not fm:
        return []
    rows = (await db.execute(
        select(Title).where(Title.filmmaker_id == fm.id).order_by(desc(Title.starts_at))
    )).scalars().all()
    return [
        {
            "id": t.id, "slug": t.slug, "title": t.title, "status": t.status,
            "live_state": t.live_state, "starts_at": t.starts_at,
            "performer_name": t.performer_name, "venue": t.venue,
            "rent_credits": t.rent_credits, "view_count": t.view_count,
            "ingest": ingest_info(t) if t.playback_id else None,
        }
        for t in rows
    ]


@router.post("/{title_id}/rotate-key")
async def rotate_stream_key(
    title_id: str,
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    """New stream key, e.g. if the old one was shared by mistake."""
    t = _owned_show((await db.execute(select(Title).where(Title.id == title_id))).scalar_one_or_none(), current_user)
    t.stream_key = new_stream_key()
    await db.commit()
    return {"ingest": ingest_info(t)}


@router.post("/{title_id}/join")
async def join_live(
    title_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a show that's already on air, for CREDITS_JOIN_LIVE (100) instead of
    the full ticket. Same access as a ticket, including the replay."""
    t = (await db.execute(
        select(Title).where(Title.id == title_id, Title.status == ContentStatus.LIVE)
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Livestream not found")
    if t.live_state != LiveState.ON_AIR:
        raise HTTPException(409, "This show isn't on air right now")
    charged, grant = await credits_svc.purchase_access(
        db, current_user.id, title_id, AccessType.RENT,
        cost=t.join_credits, label="Joined live",
    )
    return {"status": "joined", "charged": charged, "credits": t.join_credits if charged else 0,
            "expires_at": grant.expires_at}


@router.post("/{title_id}/end")
async def end_livestream(
    title_id: str,
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark the show finished (moves it to Previous Livestreams)."""
    t = _owned_show((await db.execute(select(Title).where(Title.id == title_id))).scalar_one_or_none(), current_user)
    t.live_state = LiveState.ENDED
    t.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return {"live_state": t.live_state}


@router.get("/{title_id}/atem-streaming.xml")
async def atem_streaming_xml(
    title_id: str,
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    """Streaming.xml for ATEM Software Control (Output → Live Stream → Platform →
    Load Streaming File). Adds "Bazzy Live" as a platform; the key is pasted
    separately so this file is safe to keep on a shared machine."""
    t = _owned_show((await db.execute(select(Title).where(Title.id == title_id))).scalar_one_or_none(), current_user)

    def config(res: str, fps: int, video_bps: int) -> str:
        return (f'          <config resolution="{res}" fps="{fps}">\n'
                f"            <bitrate>{video_bps}</bitrate>\n"
                f"            <audio-bitrate>128000</audio-bitrate>\n"
                f"            <keyframe-interval>2</keyframe-interval>\n"
                f"          </config>\n")

    profiles = [
        ("Streaming High",   9_000_000, 6_000_000),
        ("Streaming Medium", 6_000_000, 4_500_000),
        ("Streaming Low",    4_500_000, 3_000_000),
    ]
    body = "".join(
        f"        <profile>\n          <name>{name}</name>\n"
        + config("1080p", 60, hi) + config("1080p", 30, lo)
        + "        </profile>\n"
        for name, hi, lo in profiles
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<streaming>\n"
        "  <service>\n"
        "    <name>Bazzy Live</name>\n"
        "    <servers>\n"
        "      <server>\n"
        "        <name>Primary</name>\n"
        f"        <url>{escape(settings.INGEST_RTMP_URL)}</url>\n"
        "      </server>\n"
        "    </servers>\n"
        "    <profiles>\n"
        f"{body}"
        "    </profiles>\n"
        "  </service>\n"
        "</streaming>\n"
    )
    return Response(
        xml, media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="BazzyLive-{t.slug[:40]}.xml"'},
    )


# ── Viewer: playback pass ─────────────────────────────────────────────────────

@router.get("/{title_id}/playback")
async def playback(
    title_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Where to watch, for ticket holders. While on air: the live HLS URL plus a
    short-lived pass that MediaMTX checks. After the show: the replay."""
    t = (await db.execute(
        select(Title).where(Title.id == title_id, Title.status == ContentStatus.LIVE)
    )).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Livestream not found")
    if not t.is_free and not await credits_svc.active_access(db, current_user.id, title_id):
        raise HTTPException(402, f"Ticket required ({t.rent_credits} credits)")

    if t.live_state == LiveState.ENDED:
        return {"live_state": "ended", "hls_url": t.hls_manifest_url, "token": None}
    if t.live_state == LiveState.SCHEDULED:
        return {"live_state": "scheduled", "starts_at": t.starts_at, "hls_url": None, "token": None}

    token = jwt.encode(
        {
            # no "sub": a pass can't be used as a sign-in token
            "typ": PASS_TYPE, "uid": current_user.id, "pid": t.playback_id,
            "exp": datetime.utcnow() + timedelta(hours=settings.PLAYBACK_TOKEN_HOURS),
        },
        settings.SECRET_KEY, algorithm=settings.ALGORITHM,
    )
    return {
        "live_state": "on_air",
        "hls_url": f"{settings.LIVE_HLS_BASE}/live/{t.playback_id}/index.m3u8",
        "token": token,
    }


# ── MediaMTX callbacks ────────────────────────────────────────────────────────

def _check_hook_secret(request: Request) -> None:
    if not settings.MEDIAMTX_HOOK_SECRET:
        raise HTTPException(503, "MEDIAMTX_HOOK_SECRET is not set")
    if not secrets.compare_digest(request.query_params.get("secret", ""), settings.MEDIAMTX_HOOK_SECRET):
        raise HTTPException(401, "Bad secret")


PREVIEW_SUFFIX = "_preview"
LOOPBACK = {"127.0.0.1", "::1"}   # MediaMTX's own ffmpeg (makes the preview)


def _parse_path(path: str) -> tuple[Optional[str], bool]:
    """live/<playback_id> → (id, False); live/<playback_id>_preview → (id, True)."""
    parts = (path or "").strip("/").split("/")
    if len(parts) != 2 or parts[0] != "live" or not parts[1]:
        return None, False
    name = parts[1]
    if name.endswith(PREVIEW_SUFFIX):
        return name[: -len(PREVIEW_SUFFIX)] or None, True
    return name, False


def _playback_id_from_path(path: str) -> Optional[str]:
    pid, is_preview = _parse_path(path)
    return None if is_preview else pid


@router.post("/ingest/auth", include_in_schema=False)
async def mediamtx_auth(request: Request, db: AsyncSession = Depends(get_db)):
    """MediaMTX external auth (authMethod: http). 2xx = allow, anything else = deny."""
    _check_hook_secret(request)
    body = await request.json()
    action = body.get("action")
    pid, is_preview = _parse_path(body.get("path", ""))
    if not pid:
        raise HTTPException(401, "Unknown path")
    query = parse_qs(body.get("query") or "")
    from_mediamtx = body.get("ip") in LOOPBACK

    t = (await db.execute(select(Title).where(Title.playback_id == pid))).scalar_one_or_none()
    if not t or t.status != ContentStatus.LIVE or t.live_state == LiveState.ENDED:
        raise HTTPException(401, "Show not open")

    if is_preview:
        # Only MediaMTX's own ffmpeg writes the preview; anyone may watch it
        # while the show is on air (silent, low-res: a window into the room).
        if action == "publish" and from_mediamtx:
            return {"ok": True}
        if action == "read" and t.live_state == LiveState.ON_AIR:
            return {"ok": True}
        raise HTTPException(401, "Preview not available")

    if action == "publish":
        key = (query.get("key") or [""])[0] or body.get("password") or ""
        if t.stream_key and secrets.compare_digest(key, t.stream_key):
            return {"ok": True}
        raise HTTPException(401, "Bad stream key")

    if action == "read":
        if from_mediamtx:  # the preview encoder reading the show
            return {"ok": True}
        token = body.get("token") or (query.get("t") or query.get("jwt") or [""])[0]
        try:
            claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            raise HTTPException(401, "Bad pass")
        if claims.get("typ") == PASS_TYPE and claims.get("pid") == pid:
            return {"ok": True}
        raise HTTPException(401, "Pass is for another show")

    raise HTTPException(401, "Not allowed")


@router.post("/ingest/hook", include_in_schema=False)
async def mediamtx_hook(request: Request, event: str, path: str, db: AsyncSession = Depends(get_db)):
    """runOnReady / runOnNotReady: the ATEM feed started or stopped."""
    _check_hook_secret(request)
    pid = _playback_id_from_path(path)
    t = (await db.execute(select(Title).where(Title.playback_id == pid))).scalar_one_or_none() if pid else None
    if not t:
        raise HTTPException(404, "Unknown show")
    if event == "ready" and t.live_state != LiveState.ENDED:
        t.live_state = LiveState.ON_AIR
    elif event == "notready" and t.live_state == LiveState.ON_AIR:
        # A dropped connection also lands here; the ATEM reconnects within
        # seconds and "ready" puts it back on air. The artist ends the show.
        t.live_state = LiveState.SCHEDULED
    await db.commit()
    return {"live_state": t.live_state}
