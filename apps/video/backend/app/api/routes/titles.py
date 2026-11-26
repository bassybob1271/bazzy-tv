"""Bazzy Video — Title / Content routes"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from pydantic import BaseModel
from typing import Optional, List
from app.db.database import get_db
from app.models.models import (
    Title, ContentCategory, ContentStatus, User,
    ViewingHistory, Watchlist, ContentAccess, AccessType
)
from app.core.security import get_current_user, get_filmmaker_user
from app.services.discovery_service import DiscoveryService
from app.services.credit_service import CreditService
import uuid

router = APIRouter(prefix="/titles", tags=["titles"])
discovery = DiscoveryService()
credits_svc = CreditService()


class TitleCreate(BaseModel):
    title: str
    synopsis: str
    category: ContentCategory
    tags: List[str] = []
    year: Optional[int] = None
    runtime_minutes: Optional[int] = None
    language: str = "en"
    country: Optional[str] = None
    rating: str = "PG"
    rent_credits: int = 200
    buy_credits: int = 800
    is_free: bool = False
    is_svod_included: bool = True
    geo_restrictions: List[str] = []


class TitleOut(BaseModel):
    id: str
    title: str
    slug: str
    synopsis: Optional[str]
    category: str
    year: Optional[int]
    runtime_minutes: Optional[int]
    poster_url: Optional[str]
    trailer_url: Optional[str]
    hls_manifest_url: Optional[str]
    rent_credits: int
    buy_credits: int
    is_free: bool
    view_count: int
    completion_rate: float
    fan_vote_score: float
    status: str

    class Config:
        from_attributes = True


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/", response_model=List[TitleOut])
async def list_titles(
    category: Optional[ContentCategory] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Title).where(Title.status == ContentStatus.LIVE)
    if category:
        stmt = stmt.where(Title.category == category)
    stmt = stmt.order_by(desc(Title.completion_rate)).offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/home-rails")
async def home_rails(db: AsyncSession = Depends(get_db)):
    """All home page rails in one call."""
    return await discovery.get_home_rails(db)


@router.get("/discover")
async def discover(
    mood: Optional[str] = None,
    category: Optional[ContentCategory] = None,
    min_runtime: Optional[int] = None,
    max_runtime: Optional[int] = None,
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    if mood:
        titles = await discovery.mood_query(db, mood, limit)
    elif category:
        titles = await discovery.get_by_category(db, category, limit)
    else:
        titles = await discovery.get_trending(db, limit)
    return titles


@router.get("/{slug}", response_model=TitleOut)
async def get_title(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Title).where(Title.slug == slug, Title.status == ContentStatus.LIVE)
    )
    title = result.scalar_one_or_none()
    if not title:
        raise HTTPException(404, "Title not found")
    return title


@router.get("/{title_id}/because-you-watched")
async def because_you_watched(title_id: str, db: AsyncSession = Depends(get_db)):
    return await discovery.because_you_watched(db, title_id)


# ── Filmmaker: create + upload ─────────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_title(
    req: TitleCreate,
    current_user: User = Depends(get_filmmaker_user),
    db: AsyncSession = Depends(get_db),
):
    slug = req.title.lower().replace(" ", "-").replace("'", "")[:100] + "-" + str(uuid.uuid4())[:8]
    title = Title(
        id=str(uuid.uuid4()),
        filmmaker_id=current_user.filmmaker_profile.id if current_user.filmmaker_profile else None,
        title=req.title,
        slug=slug,
        synopsis=req.synopsis,
        category=req.category,
        tags=req.tags,
        year=req.year,
        runtime_minutes=req.runtime_minutes,
        language=req.language,
        country=req.country,
        rating=req.rating,
        rent_credits=req.rent_credits,
        buy_credits=req.buy_credits,
        is_free=req.is_free,
        is_svod_included=req.is_svod_included,
        geo_restrictions=req.geo_restrictions,
        status=ContentStatus.PENDING,
    )
    db.add(title)
    await db.commit()
    return {"title_id": title.id, "slug": title.slug, "status": "pending"}


@router.post("/{title_id}/upload-master")
async def upload_master(
    title_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_filmmaker_user),
    db: AsyncSession = Depends(get_db),
):
    """Accept master video upload. Queues transcode job via Celery."""
    import tempfile, os
    # Save to temp
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Queue async transcode (Celery task)
    from app.workers.transcode_worker import transcode_title
    transcode_title.delay(title_id, tmp_path)
    return {"status": "queued", "title_id": title_id}


# ── Viewer: access + streaming ────────────────────────────────────────────────

@router.post("/{title_id}/rent")
async def rent_title(
    title_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    charged, grant = await credits_svc.purchase_access(db, current_user.id, title_id, AccessType.RENT)
    if not charged:
        if grant.access_type == AccessType.BUY:
            return {"status": "already_owned", "permanent": True, "charged": False}
        return {"status": "already_rented", "expires_at": grant.expires_at, "charged": False}
    return {"status": "rented", "expires_days": 30, "expires_at": grant.expires_at, "charged": True}


@router.post("/{title_id}/buy")
async def buy_title(
    title_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    charged, _ = await credits_svc.purchase_access(db, current_user.id, title_id, AccessType.BUY)
    if not charged:
        return {"status": "already_owned", "permanent": True, "charged": False}
    return {"status": "purchased", "permanent": True, "charged": True}


@router.get("/{title_id}/access")
async def my_access(
    title_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Whether the signed-in viewer can watch this title (free, rented or bought)."""
    title = (await db.execute(select(Title).where(Title.id == title_id))).scalar_one_or_none()
    if not title:
        raise HTTPException(404, "Title not found")
    if title.is_free:
        return {"has_access": True, "access_type": "free", "expires_at": None}
    grant = await credits_svc.active_access(db, current_user.id, title_id)
    if not grant:
        return {"has_access": False, "access_type": None, "expires_at": None}
    return {
        "has_access": True,
        "access_type": "buy" if grant.access_type == AccessType.BUY else "rent",
        "expires_at": grant.expires_at,
    }


@router.post("/{title_id}/stream-ping")
async def stream_ping(
    title_id: str,
    minutes: int = 1,
    session_id: str = "",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Called every minute by player. Debits 1 credit/min."""
    remaining = await credits_svc.debit_stream(db, current_user.id, title_id, minutes, session_id)
    return {"credits_remaining": remaining}


@router.post("/{title_id}/vote")
async def vote(
    title_id: str,
    stars: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await discovery.submit_fan_vote(db, current_user.id, title_id, stars)
    return {"voted": stars}


# ── Watchlist ─────────────────────────────────────────────────────────────────

@router.post("/{title_id}/watchlist")
async def add_watchlist(
    title_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db.add(Watchlist(id=str(uuid.uuid4()), user_id=current_user.id, title_id=title_id))
    await db.commit()
    return {"added": True}
