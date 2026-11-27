"""Split sheets: pay everyone who worked on a show or a film.

The owner (the band, or the filmmaker) lists collaborators by email with a role and a percentage that
adds up to 100%. Every later sale's creator share is divided by it. Anyone on the sheet can see it
and what it has paid, so there are no surprises about who got what.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.database import get_db
from app.models.models import SplitPayment, SplitShare, SplitSheet, User
from app.services.splits import claim_held, invite, join_url, owns_title, validate_shares

router = APIRouter(prefix="/splits", tags=["splits"])


class ShareIn(BaseModel):
    email: str = Field(..., max_length=255)
    name: str | None = Field(None, max_length=200)
    role: str = Field(..., max_length=60)
    percent: float


class SheetIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    app: Literal["live", "tv"]
    source_ref: str = Field(..., min_length=1, max_length=120)
    shares: list[ShareIn]


class SheetEdit(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    shares: list[ShareIn] | None = None


def _out(s: SplitSheet, me: User) -> dict:
    return {
        "id": s.id, "name": s.name, "app": s.app, "source_ref": s.source_ref,
        "owner": s.owner_id == me.id,
        "shares": [{"email": x.email, "name": x.name, "role": x.role, "percent": x.bp / 100} for x in s.shares],
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


async def _visible(db: AsyncSession, sheet_id: str, me: User) -> SplitSheet:
    s = await db.get(SplitSheet, sheet_id)
    if not s or (s.owner_id != me.id and me.email.lower() not in {x.email for x in s.shares}):
        raise HTTPException(404, "No such split")
    return s


def _set_shares(sheet: SplitSheet, shares: list[ShareIn]):
    clean = validate_shares([x.model_dump() for x in shares])
    sheet.shares.clear()
    for i, x in enumerate(clean):
        sheet.shares.append(SplitShare(position=i, **x))


@router.get("")
async def my_splits(me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Splits you own, and splits you're on."""
    await claim_held(db, me)
    on = select(SplitShare.sheet_id).where(SplitShare.email == me.email.lower())
    sheets = (await db.execute(select(SplitSheet).where(or_(SplitSheet.owner_id == me.id, SplitSheet.id.in_(on)))
                              .order_by(SplitSheet.created_at.desc()))).scalars().all()
    return [_out(s, me) for s in sheets]


@router.post("", status_code=201)
async def create_split(req: SheetIn, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if req.app == "tv" and not await owns_title(db, me.id, req.source_ref):
        raise HTTPException(403, "You can only split a film you own.")
    sheet = SplitSheet(owner_id=me.id, name=req.name.strip(), app=req.app, source_ref=req.source_ref)
    _set_shares(sheet, req.shares)
    db.add(sheet)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "You already have a split for this show or film. Edit that one.")
    await invite(db, sheet, me, {x.email for x in sheet.shares})
    return _out(sheet, me)


@router.put("/{sheet_id}")
async def edit_split(sheet_id: str, req: SheetEdit, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Changes apply to sales from now on. Past sales keep the split they were paid under."""
    sheet = await _visible(db, sheet_id, me)
    if sheet.owner_id != me.id:
        raise HTTPException(403, "Only the owner can change this split.")
    if req.name:
        sheet.name = req.name.strip()
    before = {x.email for x in sheet.shares}
    if req.shares is not None:
        _set_shares(sheet, req.shares)
    await db.commit()
    await db.refresh(sheet)
    await invite(db, sheet, me, {x.email for x in sheet.shares} - before)  # only people just added
    return _out(sheet, me)


@router.delete("/{sheet_id}", status_code=204)
async def delete_split(sheet_id: str, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    sheet = await _visible(db, sheet_id, me)
    if sheet.owner_id != me.id:
        raise HTTPException(403, "Only the owner can remove this split.")
    if (await db.execute(select(func.count()).select_from(SplitPayment).where(SplitPayment.sheet_id == sheet.id))).scalar():
        raise HTTPException(409, "This split has paid people already, so it stays on record. Edit it instead.")
    await db.delete(sheet)
    await db.commit()


@router.get("/{sheet_id}/statement")
async def statement(sheet_id: str, me: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """What this split has paid, per person, plus the latest payments."""
    sheet = await _visible(db, sheet_id, me)
    rows = (await db.execute(select(SplitPayment).where(SplitPayment.sheet_id == sheet.id)
                             .order_by(SplitPayment.created_at.desc()))).scalars().all()
    per: dict[str, dict] = {}
    for p in rows:
        t = per.setdefault(p.email, {"email": p.email, "role": p.role, "credits": 0, "held_credits": 0, "join_url": None})
        t["credits"] += p.credits
        if p.user_id is None:
            t["held_credits"] += p.credits
            t["join_url"] = join_url(p.email)  # share it by text if the email got lost
    return {
        "sheet": _out(sheet, me),
        "total_credits": sum(p.credits for p in rows),
        "sales": len({p.sale_ref for p in rows}),
        "people": list(per.values()),
        "recent": [{"sale_ref": p.sale_ref, "email": p.email, "role": p.role, "credits": p.credits,
                    "held": p.user_id is None, "at": p.created_at.isoformat() if p.created_at else None} for p in rows[:50]],
    }
