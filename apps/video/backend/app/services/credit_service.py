"""Bazzy Video — Credit Ledger Service
$10 = 1,000 credits. Same model as Anthropic / Bazzy Live.
Payout waterfall: 3% processing + 7% delivery → 80% filmmaker / 10% ops / 10% reserve
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from app.core.config import settings
from app.models.models import (
    User, CreditTransaction, FilmmakerEarning, Payout,
    TransactionType, ContentAccess, AccessType, Title, FilmmakerProfile
)
from datetime import datetime, timedelta, timezone
import uuid

try:
    import stripe
    stripe.api_key = settings.STRIPE_SECRET_KEY
except Exception:
    stripe = None


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

        if not stripe:
            raise HTTPException(503, "Stripe not configured")

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
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
            success_url="http://localhost:3000/wallet?success=1",
            cancel_url="http://localhost:3000/wallet",
            metadata={"user_id": user_id, "tier": tier, "credits": total_credits},
        )
        return session.url

    async def fulfill_credit_purchase(self, db: AsyncSession, user_id: str,
                                       credits: int, stripe_payment_id: str,
                                       usd_amount: float):
        """Called by Stripe webhook on payment_intent.succeeded"""
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                credit_balance=User.credit_balance + credits,
                lifetime_credits=User.lifetime_credits + credits,
            )
        )
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
        credits_to_debit = minutes * settings.CREDITS_STREAM_PER_MIN

        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(404, "User not found")

        # Free titles, and titles the viewer has rented (unexpired) or bought,
        # are already paid for: no per-minute charge.
        title = (await db.execute(select(Title).where(Title.id == title_id))).scalar_one_or_none()
        if not title:
            raise HTTPException(404, "Title not found")
        if title.is_free or await self.active_access(db, user_id, title_id):
            return user.credit_balance
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
        )
        db.add(txn)
        await self._credit_filmmaker(db, title_id, credits_to_debit)
        await db.commit()
        return user.credit_balance

    # ── Rent / Buy ────────────────────────────────────────────────────────────

    async def active_access(self, db: AsyncSession, user_id: str,
                            title_id: str) -> "ContentAccess | None":
        """Best current grant for this user+title: a purchase beats a rental,
        a later-expiring rental beats an earlier one. Expired rentals don't count."""
        result = await db.execute(
            select(ContentAccess).where(
                ContentAccess.user_id == user_id,
                ContentAccess.title_id == title_id,
            )
        )
        now = datetime.utcnow()
        best = None
        for grant in result.scalars():
            if grant.access_type == AccessType.BUY or grant.expires_at is None:
                return grant
            expires = grant.expires_at
            if expires.tzinfo is not None:  # Postgres returns aware, SQLite naive
                expires = expires.astimezone(timezone.utc).replace(tzinfo=None)
            if expires > now and (best is None or expires > best[0]):
                best = (expires, grant)
        return best[1] if best else None

    async def purchase_access(self, db: AsyncSession, user_id: str, title_id: str,
                               access_type: AccessType) -> tuple[bool, "ContentAccess"]:
        """Debit credits for rent or buy, grant access.

        Returns (charged, grant). If the user already has access that covers the
        request (an owned title, or an unexpired rental when renting), nothing is
        charged and the existing grant is returned. Buying a title you only rent
        is still charged: it upgrades the rental to permanent.
        """
        result_user  = await db.execute(select(User).where(User.id == user_id))
        result_title = await db.execute(select(Title).where(Title.id == title_id))
        user  = result_user.scalar_one_or_none()
        title = result_title.scalar_one_or_none()
        if not user:
            raise HTTPException(404, "User not found")
        if not title:
            raise HTTPException(404, "Title not found")

        existing = await self.active_access(db, user_id, title_id)
        if existing and (existing.access_type == AccessType.BUY
                         or access_type == AccessType.RENT):
            return False, existing

        credits_cost = (
            title.rent_credits if access_type == AccessType.RENT else title.buy_credits
        )
        if user.credit_balance < credits_cost:
            raise HTTPException(402, f"Need {credits_cost} credits, have {user.credit_balance}")

        user.credit_balance -= credits_cost

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
        return True, access

    # ── Filmmaker credit (payout waterfall) ───────────────────────────────────

    async def _credit_filmmaker(self, db: AsyncSession, title_id: str, gross_credits: int):
        """Apply payout waterfall and credit filmmaker's ledger."""
        result = await db.execute(select(Title).where(Title.id == title_id))
        title = result.scalar_one_or_none()
        # No filmmaker attached (seed data) — skip silently
        if not title or not title.filmmaker_id:
            return

        net_credits = int(gross_credits * (1 - settings.PLATFORM_PROCESSING_FEE_PCT
                                             - settings.PLATFORM_DELIVERY_FEE_PCT))
        fm_credits  = int(net_credits * settings.FILMMAKER_SHARE_PCT)

        earning = FilmmakerEarning(
            id=str(uuid.uuid4()),
            filmmaker_id=title.filmmaker_id,
            title_id=title_id,
            credits_earned=fm_credits,
            usd_equivalent=fm_credits / settings.CREDITS_PER_DOLLAR,
        )
        db.add(earning)

        await db.execute(
            update(FilmmakerProfile)
            .where(FilmmakerProfile.id == title.filmmaker_id)
            .values(total_earned_credits=FilmmakerProfile.total_earned_credits + fm_credits)
        )

    # ── Payout (Stripe Connect) ────────────────────────────────────────────────

    async def trigger_payout(self, db: AsyncSession, filmmaker_id: str) -> dict:
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

        result_fm = await db.execute(
            select(FilmmakerProfile).where(FilmmakerProfile.id == filmmaker_id)
        )
        fm = result_fm.scalar_one_or_none()
        if not fm or not fm.stripe_connect_id:
            raise HTTPException(400, "Stripe Connect account not set up")

        if not stripe:
            raise HTTPException(503, "Stripe not configured")

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
