"""Bazzy Video — Filmmaker Portal routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from pydantic import BaseModel
from typing import Optional
from app.db.database import get_db
from app.models.models import (
    User, FilmmakerProfile, Title, FilmmakerEarning, Payout, ContentStatus
)
from app.core.security import get_creator_user, get_filmmaker_user
from app.services.credit_service import CreditService
import stripe
from app.core.config import settings

router = APIRouter(prefix="/filmmaker", tags=["filmmaker"])
credits_svc = CreditService()
stripe.api_key = settings.STRIPE_SECRET_KEY


@router.get("/dashboard")
async def dashboard(
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    """Main filmmaker dashboard — earnings, titles, analytics."""
    fm = current_user.filmmaker_profile
    if not fm:
        raise HTTPException(404, "Filmmaker profile not found")

    # Title stats
    result = await db.execute(
        select(Title).where(Title.filmmaker_id == fm.id)
    )
    titles = result.scalars().all()

    # Unsettled earnings
    earn_result = await db.execute(
        select(func.sum(FilmmakerEarning.credits_earned),
               func.sum(FilmmakerEarning.usd_equivalent))
        .where(FilmmakerEarning.filmmaker_id == fm.id,
               FilmmakerEarning.settled == False)
    )
    unsettled_credits, unsettled_usd = earn_result.one()

    return {
        "filmmaker_id": fm.id,
        "display_name": current_user.display_name,
        "stripe_connected": bool(fm.stripe_connect_id),
        "kyc_verified": fm.stripe_kyc_verified,
        "total_earned_credits": fm.total_earned_credits,
        "total_paid_out_usd": fm.total_paid_out_usd,
        "unsettled_credits": unsettled_credits or 0,
        "unsettled_usd": round(unsettled_usd or 0, 2),
        "payout_ready": (unsettled_usd or 0) >= settings.MIN_PAYOUT_USD,
        "wallet_credits": current_user.credit_balance,
        "titles": [
            {
                "id": t.id, "title": t.title, "status": t.status,
                "view_count": t.view_count, "completion_rate": round(t.completion_rate, 3),
                "fan_vote_score": round(t.fan_vote_score, 3),
                "revenue_velocity": t.revenue_velocity,
            }
            for t in titles
        ],
    }


@router.get("/analytics/{title_id}")
async def title_analytics(
    title_id: str,
    current_user: User = Depends(get_filmmaker_user),
    db: AsyncSession = Depends(get_db),
):
    """Per-title analytics: earnings, views, completion curve."""
    result = await db.execute(
        select(Title).where(
            Title.id == title_id,
            Title.filmmaker_id == current_user.filmmaker_profile.id,
        )
    )
    title = result.scalar_one_or_none()
    if not title:
        raise HTTPException(404, "Title not found or access denied")

    earn_result = await db.execute(
        select(func.sum(FilmmakerEarning.credits_earned),
               func.sum(FilmmakerEarning.usd_equivalent),
               func.count(FilmmakerEarning.id))
        .where(FilmmakerEarning.title_id == title_id)
    )
    total_credits, total_usd, num_transactions = earn_result.one()

    return {
        "title_id": title_id,
        "title_name": title.title,
        "view_count": title.view_count,
        "completion_rate": round(title.completion_rate * 100, 1),
        "fan_vote_score": round(title.fan_vote_score * 5, 2),
        "revenue_velocity_7d": title.revenue_velocity,
        "total_earned_credits": total_credits or 0,
        "total_earned_usd": round(total_usd or 0, 2),
        "num_transactions": num_transactions or 0,
    }


@router.post("/connect-stripe")
async def connect_stripe(
    code: str,
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    """Exchange Stripe Connect OAuth code for account ID."""
    response = stripe.OAuth.token(grant_type="authorization_code", code=code)
    connect_id = response["stripe_user_id"]

    from sqlalchemy import update
    await db.execute(
        update(FilmmakerProfile)
        .where(FilmmakerProfile.user_id == current_user.id)
        .values(stripe_connect_id=connect_id)
    )
    await db.commit()
    return {"stripe_connected": True, "connect_id": connect_id}


@router.post("/request-payout")
async def request_payout(
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    fm = current_user.filmmaker_profile
    if not fm:
        raise HTTPException(404, "Filmmaker profile not found")
    result = await credits_svc.trigger_payout(db, fm.id)
    return result


@router.get("/payout-history")
async def payout_history(
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    fm = current_user.filmmaker_profile
    result = await db.execute(
        select(Payout)
        .where(Payout.filmmaker_id == fm.id)
        .order_by(desc(Payout.created_at))
        .limit(50)
    )
    return result.scalars().all()


class EarningsToWallet(BaseModel):
    credits: Optional[int] = None   # omit to move everything earned so far


@router.post("/earnings-to-wallet")
async def earnings_to_wallet(
    req: EarningsToWallet,
    current_user: User = Depends(get_creator_user),
    db: AsyncSession = Depends(get_db),
):
    """Spend what you earn: move earned credits into your Bazzy wallet, the one balance for films,
    Bazzy Live tickets and BazzyBox storage. Moved credits are no longer part of a bank payout."""
    fm = current_user.filmmaker_profile
    if not fm:
        raise HTTPException(404, "No earnings yet")
    return await credits_svc.earnings_to_wallet(db, current_user, fm.id, req.credits)
