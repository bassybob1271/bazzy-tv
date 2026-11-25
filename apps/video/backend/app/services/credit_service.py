"""Bazzy Video — Credit Ledger Service
$10 = 1,000 credits. Same model as Anthropic / Bazzy Live.
Payout waterfall: 3% processing + 7% delivery → 80% filmmaker / 10% ops / 10% reserve
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import stripe
from app.core.config import settings
from app.models.models import (
    User, CreditTransaction, FilmmakerEarning, Payout,
    TransactionType, ContentAccess, AccessType, Title
)
from datetime import datetime, timedelta
import uuid

stripe.api_key = settings.STRIPE_SECRET_KEY


class CreditService:

    # ── Purchase credits via Stripe Checkout ──────────────────────────────────

    CREDIT_TIERS = {
        "starter":   {"usd": 10.00,  "credits": 1000, "bonus": 0},
        "plus":      {"usd": 25.00,  "credits": 2750, "bonus": 250},
        "pro":       {"usd": 50.00,  "credits": 6000, "bonus": 1000},
        "cinephile": {"usd": 100.00, "credits": 13000, "bonus": 3000},
    }

    async def create_checkout_session(self, user_id: str, tier: str) -> str:
        """Create Stripe Checkout session for credit purchase. Returns checkout URL."""
        if tier not in self.CREDIT_TIERS:
            raise HTTPException(400, f"Invalid tier. Choose: {list(self.CREDIT_TIERS.keys())}")

        t = self.CREDIT_TIERS[tier]
        total_credits = t["credits"] + t["bonus"]

        session = stripe.checkout.Session.create(
            payment_method_types=["card", "apple_pay", "google_pay", "us_bank_account"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(t["usd"] * 100),
                    "product_data": {
                        "name": f"Bazzy Video — {total_credits:,} Credits",
                        "description": f"{t['credits']:,} credits" + (f" + {t['bonus']:,} bonus" if t["bonus"] else ""),
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url="https://video.bazzy.tv/wallet?success=1",
            cancel_url="https://video.bazzy.tv/wallet",
            metadata={"user_id": user_id, "tier": tier, "credits": total_credits},
        )
        return session.url

    async def fulfill_credit_purchase(self, db: AsyncSession, user_id: str,
                                       credits: int, stripe_payment_id: str,
                                       usd_amount: float):
        """Called by Stripe webhook on payment_intent.succeeded"""
        # Add credits to user wallet
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                credit_balance=User.credit_balance + credits,
                lifetime_credits=User.lifetime_credits + credits,
            )
        )
        # Log transaction
        txn = CreditTransaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            transaction_type=TransactionType.CREDIT_PURCHASE,
            credits_delta=credits,
            usd_equivalent=usd_amount,
            stripe_payment_id=stripe_payment_id,
            description=f"Purchased {credits:,} credits",
        )
        db.add(txn)
        await db.commit()

    # ── Stream debit (1 cr/min while watching) ────────────────────────────────

    async def debit_stream(self, db: AsyncSession, user_id: str, title_id: str,
                            minutes: int, session_id: str) -> int:
        """Debit streaming credits. Returns remaining balance."""
        credits_to_debit = minutes * settings.CREDITS_STREAM_PER_MIN

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(404, "User not found")
        if user.credit_balance < credits_to_debit:
            raise HTTPException(402, "Insufficient credits")

        user.credit_balance -= credits_to_debit

        txn = CreditTransaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title_id=title_id,
            transaction_type=TransactionType.STREAM_DEBIT,
            credits_delta=-credits_to_debit,
            description=f"Streamed {minutes} minutes",
            extra_data={"session_id": session_id},
        )
        db.add(txn)

        # Credit filmmaker (async — via Kafka in production, inline for MVP)
        await self._credit_filmmaker(db, title_id, credits_to_debit)

        await db.commit()
        return user.credit_balance

    # ── Rent / Buy ────────────────────────────────────────────────────────────

    async def purchase_access(self, db: AsyncSession, user_id: str, title_id: str,
                               access_type: AccessType):
        """Debit credits for rent or buy, grant access."""
        result_user  = await db.execute(select(User).where(User.id == user_id))
        result_title = await db.execute(select(Title).where(Title.id == title_id))
        user  = result_user.scalar_one_or_none()
        title = result_title.scalar_one_or_none()
        if not user or not title:
            raise HTTPException(404, "User or title not found")

        credits_cost = (
            title.rent_credits if access_type == AccessType.RENT else title.buy_credits
        )
        if user.credit_balance < credits_cost:
            raise HTTPException(402, f"Need {credits_cost} credits, have {user.credit_balance}")

        user.credit_balance -= credits_cost

        # Grant access
        expires = datetime.utcnow() + timedelta(days=30) if access_type == AccessType.RENT else None
        access = ContentAccess(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title_id=title_id,
            access_type=access_type,
            expires_at=expires,
        )
        db.add(access)

        txn_type = TransactionType.RENT_DEBIT if access_type == AccessType.RENT else TransactionType.BUY_DEBIT
        txn = CreditTransaction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title_id=title_id,
            transaction_type=txn_type,
            credits_delta=-credits_cost,
            description=f"{'Rented' if access_type == AccessType.RENT else 'Purchased'}: {title.title}",
        )
        db.add(txn)
        await self._credit_filmmaker(db, title_id, credits_cost)
        await db.commit()

    # ── Filmmaker credit (payout waterfall) ───────────────────────────────────

    async def _credit_filmmaker(self, db: AsyncSession, title_id: str, gross_credits: int):
        """Apply payout waterfall and credit filmmaker's ledger."""
        result = await db.execute(select(Title).where(Title.id == title_id))
        title = result.scalar_one_or_none()
        if not title:
            return

        # Waterfall: 3% processing + 7% delivery = 10% gross fees
        net_credits  = int(gross_credits * (1 - settings.PLATFORM_PROCESSING_FEE_PCT
                                              - settings.PLATFORM_DELIVERY_FEE_PCT))
        fm_credits   = int(net_credits * settings.FILMMAKER_SHARE_PCT)

        earning = FilmmakerEarning(
            id=str(uuid.uuid4()),
            filmmaker_id=title.filmmaker_id,
            title_id=title_id,
            credits_earned=fm_credits,
            usd_equivalent=fm_credits / settings.CREDITS_PER_DOLLAR,
        )
        db.add(earning)

        # Update filmmaker lifetime total
        await db.execute(
            update(type(title.filmmaker))
            .where(type(title.filmmaker).id == title.filmmaker_id)
            .values(total_earned_credits=type(title.filmmaker).total_earned_credits + fm_credits)
        )

    # ── Payout (Stripe Connect) ────────────────────────────────────────────────

    async def trigger_payout(self, db: AsyncSession, filmmaker_id: str) -> dict:
        """Aggregate unsettled earnings and trigger Stripe Connect transfer."""
        from sqlalchemy import func as sqlfunc
        result = await db.execute(
            select(sqlfunc.sum(FilmmakerEarning.usd_equivalent))
            .where(
                FilmmakerEarning.filmmaker_id == filmmaker_id,
                FilmmakerEarning.settled == False,
            )
        )
        total_usd = result.scalar() or 0.0

        if total_usd < settings.MIN_PAYOUT_USD:
            raise HTTPException(400, f"Minimum payout is ${settings.MIN_PAYOUT_USD}. Balance: ${total_usd:.2f}")

        from app.models.models import FilmmakerProfile
        result_fm = await db.execute(
            select(FilmmakerProfile).where(FilmmakerProfile.id == filmmaker_id)
        )
        fm = result_fm.scalar_one_or_none()
        if not fm or not fm.stripe_connect_id:
            raise HTTPException(400, "Stripe Connect account not set up")

        # Stripe transfer
        transfer = stripe.Transfer.create(
            amount=int(total_usd * 100),
            currency="usd",
            destination=fm.stripe_connect_id,
            description=f"Bazzy Video payout — {filmmaker_id[:8]}",
        )

        payout = Payout(
            id=str(uuid.uuid4()),
            filmmaker_id=filmmaker_id,
            amount_usd=total_usd,
            stripe_transfer_id=transfer.id,
            status="sent",
            paid_at=datetime.utcnow(),
        )
        db.add(payout)

        # Mark earnings as settled
        await db.execute(
            update(FilmmakerEarning)
            .where(FilmmakerEarning.filmmaker_id == filmmaker_id,
                   FilmmakerEarning.settled == False)
            .values(settled=True, payout_id=payout.id)
        )
        await db.execute(
            update(FilmmakerProfile)
            .where(FilmmakerProfile.id == filmmaker_id)
            .values(total_paid_out_usd=FilmmakerProfile.total_paid_out_usd + total_usd)
        )
        await db.commit()
        return {"payout_id": payout.id, "amount_usd": total_usd, "stripe_transfer_id": transfer.id}
