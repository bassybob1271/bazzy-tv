"""One wallet for every Bazzy app, like an Apple account.

A member's credits live here, on Bazzy TV. BazzyBox and Bazzy Live don't keep balances of their own:
their servers read and charge this one, so credits bought anywhere pay for films, concert tickets and
storage alike. 1 credit = $0.01.

Server to server only. The app authenticates with its OAuth client id and secret (HTTP Basic), and its
OAUTH_CLIENTS entry must say "wallet": true. A member is named by the `sub` that /oauth/userinfo gave
the app, so an app can only touch wallets of people who signed in to it with Bazzy TV.

  GET  /api/v1/apps/wallet/{sub}           -> {"credits": 1234}
  POST /api/v1/apps/wallet/{sub}/entries   {"credits": -300, "ref": "...", "note": "..."}
       credits < 0 charges, > 0 credits. `ref` is unique per app: sending it again changes nothing.
       A charge larger than the balance is refused with 402 and nothing changes.
"""
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.provider import _basic_auth, _clients
from app.db.database import get_db
from app.models.models import AppWalletEntry, CreditTransaction, TransactionType, User

router = APIRouter(prefix="/apps/wallet", tags=["apps"])


def wallet_client(authorization: str | None = Header(None)) -> dict:
    basic = _basic_auth(authorization)
    c = _clients().get(basic[0]) if basic else None
    if not c or not basic[1] or not secrets.compare_digest(str(c.get("client_secret", "")), basic[1]):
        raise HTTPException(401, "app authentication failed")
    if not c.get("wallet"):
        raise HTTPException(403, "this app may not use the shared wallet")
    return c


async def _member(db: AsyncSession, sub: str) -> User:
    user = await db.get(User, sub)
    if not user or not user.is_active:
        raise HTTPException(404, "no such member")
    return user


class Entry(BaseModel):
    credits: int = Field(..., ne=0, ge=-10_000_000, le=10_000_000)
    ref: str = Field(..., min_length=1, max_length=120)
    note: str = Field("", max_length=300)


@router.get("/{sub}")
async def balance(sub: str, c: dict = Depends(wallet_client), db: AsyncSession = Depends(get_db)):
    return {"credits": (await _member(db, sub)).credit_balance}


@router.post("/{sub}/entries")
async def entry(sub: str, e: Entry, c: dict = Depends(wallet_client), db: AsyncSession = Depends(get_db)):
    await _member(db, sub)
    app_name = c.get("name") or c["client_id"]
    key = f"{c['client_id']}:{e.ref}"

    prior = await db.get(AppWalletEntry, key)
    if prior:
        bal = (await db.execute(select(User.credit_balance).where(User.id == sub))).scalar_one()
        if prior.user_id != sub or prior.credits != e.credits:
            raise HTTPException(409, "this ref was already used for a different entry")
        return {"applied": False, "accepted": prior.applied, "credits": bal}

    # Charge only if the balance covers it, in the same statement that checks it.
    res = await db.execute(
        update(User)
        .where(User.id == sub, User.credit_balance + e.credits >= 0)
        .values(credit_balance=User.credit_balance + e.credits)
        .returning(User.credit_balance)
    )
    new_bal = res.scalar_one_or_none()
    if new_bal is None:
        await db.rollback()
        bal = (await db.execute(select(User.credit_balance).where(User.id == sub))).scalar_one()
        raise HTTPException(402, detail={"error": "insufficient credits", "credits": bal})

    txn = CreditTransaction(
        id=str(uuid.uuid4()),
        user_id=sub,
        transaction_type=TransactionType.APP_DEBIT if e.credits < 0 else TransactionType.APP_CREDIT,
        credits_delta=e.credits,
        description=f"{app_name} · {e.note}" if e.note else app_name,
        extra_data={"app": c["client_id"], "ref": e.ref},
    )
    db.add(txn)
    await db.flush()
    db.add(AppWalletEntry(id=key, client_id=c["client_id"], user_id=sub, credits=e.credits, txn_id=txn.id))
    try:
        await db.commit()
    except IntegrityError:
        # Same ref raced in from a retry: theirs won, ours rolls back whole.
        await db.rollback()
        bal = (await db.execute(select(User.credit_balance).where(User.id == sub))).scalar_one()
        return {"applied": False, "accepted": True, "credits": bal}
    return {"applied": True, "accepted": True, "credits": new_bal}
