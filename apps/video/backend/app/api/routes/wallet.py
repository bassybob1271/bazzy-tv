"""Bazzy Video — Wallet & Credit routes"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.db.database import get_db
from app.models.models import User, CreditTransaction
from app.core.security import get_current_user
from app.services.credit_service import CreditService
import stripe
from app.core.config import settings

router = APIRouter(prefix="/wallet", tags=["wallet"])
credits_svc = CreditService()
stripe.api_key = settings.STRIPE_SECRET_KEY


class CheckoutRequest(BaseModel):
    tier: str   # starter / plus / pro / cinephile


@router.get("/")
async def get_wallet(current_user: User = Depends(get_current_user)):
    return {
        "credit_balance": current_user.credit_balance,
        "lifetime_credits": current_user.lifetime_credits,
        "usd_equivalent": round(current_user.credit_balance / settings.CREDITS_PER_DOLLAR, 2),
    }


@router.post("/checkout")
async def create_checkout(
    req: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    url = await credits_svc.create_checkout_session(current_user.id, req.tier)
    return {"checkout_url": url}


@router.get("/tiers")
async def list_tiers():
    return CreditService.CREDIT_TIERS


@router.get("/transactions")
async def transaction_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import desc
    result = await db.execute(
        select(CreditTransaction)
        .where(CreditTransaction.user_id == current_user.id)
        .order_by(desc(CreditTransaction.created_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/stripe-webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Stripe webhook endpoint — fulfills credit purchases."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid webhook signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        meta = session.get("metadata", {})
        await credits_svc.fulfill_credit_purchase(
            db,
            user_id=meta["user_id"],
            credits=int(meta["credits"]),
            stripe_payment_id=session["payment_intent"],
            usd_amount=session["amount_total"] / 100,
        )

    return {"received": True}
