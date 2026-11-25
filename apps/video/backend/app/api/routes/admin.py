"""Bazzy Video — Admin Backend routes"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, desc
from pydantic import BaseModel
from typing import Optional
from app.db.database import get_db
from app.models.models import (
    Title, ContentStatus, User, FilmmakerProfile,
    CreditTransaction, FilmmakerEarning, ViewingHistory
)
from app.core.security import get_admin_user

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Content queue ─────────────────────────────────────────────────────────────

@router.get("/content/queue")
async def content_queue(
    status: Optional[ContentStatus] = ContentStatus.REVIEW,
    limit: int = 50,
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Title).where(Title.status == status)
        .order_by(Title.created_at)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/content/{title_id}/approve")
async def approve_title(
    title_id: str,
    editorial_score: float = 0.0,
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    await db.execute(
        update(Title).where(Title.id == title_id).values(
            status=ContentStatus.LIVE,
            editorial_score=editorial_score,
            published_at=datetime.utcnow(),
        )
    )
    await db.commit()
    return {"approved": title_id}


@router.post("/content/{title_id}/reject")
async def reject_title(
    title_id: str,
    reason: str = "",
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Title).where(Title.id == title_id)
        .values(status=ContentStatus.REJECTED)
    )
    await db.commit()
    return {"rejected": title_id, "reason": reason}


@router.post("/content/{title_id}/editorial-score")
async def set_editorial_score(
    title_id: str,
    score: float,
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    if not 0 <= score <= 1:
        raise HTTPException(400, "Score must be 0.0 – 1.0")
    await db.execute(
        update(Title).where(Title.id == title_id).values(editorial_score=score)
    )
    await db.commit()
    return {"title_id": title_id, "editorial_score": score}


# ── Platform metrics ──────────────────────────────────────────────────────────

@router.get("/metrics")
async def platform_metrics(
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    total_users  = await db.execute(select(func.count(User.id)))
    total_titles = await db.execute(select(func.count(Title.id)).where(Title.status == ContentStatus.LIVE))
    total_txns   = await db.execute(select(func.count(CreditTransaction.id)))
    total_credits_sold = await db.execute(
        select(func.sum(CreditTransaction.credits_delta))
        .where(CreditTransaction.transaction_type == "credit_purchase")
    )
    total_fm_paid = await db.execute(select(func.sum(FilmmakerEarning.usd_equivalent)))

    return {
        "total_users":          total_users.scalar(),
        "live_titles":          total_titles.scalar(),
        "total_transactions":   total_txns.scalar(),
        "total_credits_sold":   total_credits_sold.scalar() or 0,
        "total_filmmaker_paid_usd": round(total_fm_paid.scalar() or 0, 2),
    }


@router.get("/ledger")
async def credit_ledger(
    limit: int = 100,
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CreditTransaction)
        .order_by(desc(CreditTransaction.created_at))
        .limit(limit)
    )
    return result.scalars().all()


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    limit: int = 50,
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).order_by(desc(User.created_at)).limit(limit)
    )
    return result.scalars().all()


@router.post("/users/{user_id}/grant-credits")
async def grant_credits(
    user_id: str,
    credits: int,
    reason: str = "promo",
    current_user=Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    from app.models.models import CreditTransaction, TransactionType
    await db.execute(
        update(User).where(User.id == user_id)
        .values(credit_balance=User.credit_balance + credits,
                lifetime_credits=User.lifetime_credits + credits)
    )
    txn = CreditTransaction(
        id=str(uuid.uuid4()), user_id=user_id,
        transaction_type=TransactionType.PROMO_GRANT,
        credits_delta=credits,
        description=f"Admin grant: {reason}",
    )
    db.add(txn)
    await db.commit()
    return {"granted": credits, "user_id": user_id}
