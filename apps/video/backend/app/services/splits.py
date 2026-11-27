"""Payout splits: one sale, many collaborators.

A band selling tickets to a Bazzy Live show (or a filmmaker renting a film) can list everyone who made
it: the venue, producers, engineers, openers, the rest of the band. The creator share of each sale
(see credit_service.creator_share) is divided by that list, and each person's cut lands in their own
earnings: spend it from the Bazzy wallet, or cash it out. Someone who isn't on Bazzy yet has their cut
held under their email and claimed the moment they sign in with that email verified.

Money is whole credits. Each cut is rounded down; the credits left over by rounding go to the first
person on the sheet (put the band first), so the cuts always add up to the sale.
"""
import uuid
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import FilmmakerProfile, SplitPayment, SplitShare, SplitSheet, User
from app.services.credit_service import CreditService

FULL = 10_000  # basis points in 100%
MAX_SHARES = 50


def percent_to_bp(p) -> int:
    try:
        d = Decimal(str(p))
    except InvalidOperation:
        raise HTTPException(400, f"{p!r} isn't a percentage")
    bp = d * 100
    if bp != bp.to_integral_value() or not (0 < bp <= FULL):
        raise HTTPException(400, f"Use percentages between 0.01 and 100, to two decimals (got {p}).")
    return int(bp)


def validate_shares(shares: list[dict]) -> list[dict]:
    if not shares:
        raise HTTPException(400, "Add at least one person to the split.")
    if len(shares) > MAX_SHARES:
        raise HTTPException(400, f"A split can have up to {MAX_SHARES} people.")
    out, seen = [], set()
    for s in shares:
        email = str(s.get("email", "")).strip().lower()
        if "@" not in email or len(email) > 255:
            raise HTTPException(400, f"{email or 'A collaborator'} needs a valid email.")
        if email in seen:
            raise HTTPException(400, f"{email} is listed twice. Give them one line with their total.")
        seen.add(email)
        role = str(s.get("role", "")).strip()[:60]
        if not role:
            raise HTTPException(400, f"Give {email} a role, like venue or producer.")
        out.append({"email": email, "name": (str(s.get("name") or "").strip()[:200] or None), "role": role, "bp": percent_to_bp(s.get("percent"))})
    total = sum(s["bp"] for s in out)
    if total != FULL:
        raise HTTPException(400, f"The split adds up to {total / 100:g}%. It has to be exactly 100%.")
    return out


def allocate(credits: int, shares: list[SplitShare]) -> list[int]:
    cuts = [credits * s.bp // FULL for s in shares]
    cuts[0] += credits - sum(cuts)
    return cuts


async def sheet_for(db: AsyncSession, owner_id: str, app: str, source_ref: str) -> SplitSheet | None:
    return (await db.execute(select(SplitSheet).where(
        SplitSheet.owner_id == owner_id, SplitSheet.app == app, SplitSheet.source_ref == source_ref))).scalar_one_or_none()


async def _verified_member(db: AsyncSession, email: str) -> User | None:
    u = (await db.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    return u if u and u.is_active and u.is_verified else None


async def pay_sale(db: AsyncSession, sheet: SplitSheet, creator_credits: int, sale_ref: str, title_id: str | None = None) -> list[dict]:
    """Divide one sale's creator share by the sheet. Doesn't commit."""
    svc = CreditService()
    paid = []
    for share, cut in zip(sheet.shares, allocate(creator_credits, sheet.shares)):
        if cut <= 0:
            continue
        member = await _verified_member(db, share.email)
        pay = SplitPayment(id=str(uuid.uuid4()), sheet_id=sheet.id, sale_ref=sale_ref, email=share.email, role=share.role, credits=cut)
        if member:
            pay.user_id = member.id
            pay.earning_id = await svc.add_earning(db, member.id, cut, title_id=title_id)
        db.add(pay)
        paid.append({"email": share.email, "role": share.role, "credits": cut, "held": member is None})
    return paid


async def claim_held(db: AsyncSession, user: User) -> int:
    """Move cuts held under this member's verified email into their earnings. Returns credits claimed."""
    if not user.is_verified:
        return 0
    held = (await db.execute(select(SplitPayment).where(
        func.lower(SplitPayment.email) == user.email.lower(), SplitPayment.user_id.is_(None)))).scalars().all()
    if not held:
        return 0
    svc = CreditService()
    for p in held:
        p.user_id = user.id
        p.earning_id = await svc.add_earning(db, user.id, p.credits)
    await db.commit()
    return sum(p.credits for p in held)


def join_url(email: str) -> str:
    from urllib.parse import urlencode
    from app.core.config import settings
    return f"{settings.PUBLIC_URL.rstrip('/')}/auth/register?" + urlencode({"email": email, "redirect": "/splits"})


async def invite(db: AsyncSession, sheet: SplitSheet, owner: User, emails: set[str]):
    """Tell people they're on a split. Anyone not on Bazzy gets a join link: a few minutes to sign up
    with this email and their cut, held until then, lands in their earnings."""
    import html
    from app.core.config import settings
    from app.services import mailer
    who = owner.display_name or owner.email
    for share in sheet.shares:
        if share.email not in emails or share.email == owner.email.lower():
            continue
        member = (await db.execute(select(User).where(func.lower(User.email) == share.email))).scalar_one_or_none()
        pct = f"{share.bp / 100:g}%"
        if member:
            url = f"{settings.PUBLIC_URL.rstrip('/')}/splits"
            body = f"{who} added you to the split for {sheet.name} as {share.role}, {pct} of every sale. Your cut goes straight into your Bazzy earnings."
            cta = "See the split"
        else:
            url = join_url(share.email)
            body = (f"{who} added you to the split for {sheet.name} as {share.role}, {pct} of every sale. "
                    f"Create your free Bazzy account with {share.email} and your cut, including anything already earned, "
                    "lands in your earnings. It takes about five minutes. Spend it on films, Bazzy Live and BazzyBox, or cash it out.")
            cta = "Claim your cut"
        await mailer.send(share.email, f"You're on the split for {sheet.name}", f"{body}\n\n{url}",
                          mailer.button_html(html.escape(f"You're on the split for {sheet.name}"), html.escape(body), cta, html.escape(url)))


async def owns_title(db: AsyncSession, user_id: str, title_id: str) -> bool:
    from app.models.models import Title
    t = (await db.execute(select(Title.id).join(FilmmakerProfile, Title.filmmaker_id == FilmmakerProfile.id)
                          .where(Title.id == title_id, FilmmakerProfile.user_id == user_id))).first()
    return t is not None
