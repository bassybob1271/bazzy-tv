"""Bazzy Video — Auth routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.db.database import get_db
from app.models.models import User, UserRole, FilmmakerProfile
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import settings
from app.services import mailer
from datetime import timedelta
from jose import JWTError, jwt
import html
import uuid

VERIFY_TYP = "verify_email"


def verify_link(user: User) -> str:
    token = create_access_token({"sub": user.id, "email": user.email.lower(), "typ": VERIFY_TYP},
                                timedelta(hours=settings.EMAIL_VERIFY_TTL_HOURS))
    return f"{settings.PUBLIC_URL.rstrip('/')}/auth/verify?token={token}"


async def send_verification(user: User):
    url = verify_link(user)
    await mailer.send(
        user.email, "Confirm your email for Bazzy TV",
        f"Confirm your email to finish setting up Bazzy TV: {url}\n\nOne account for films, Bazzy Live and BazzyBox.",
        mailer.button_html("Confirm your email", "One tap and your Bazzy account is ready: films, Bazzy Live concerts and BazzyBox storage, one wallet. If anyone has paid you through a split, it lands as soon as you confirm.", "Confirm email", html.escape(url)),
    )

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    display_name: str
    is_filmmaker: bool = False
    bio: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name,
        role=UserRole.FILMMAKER if req.is_filmmaker else UserRole.VIEWER,
        credit_balance=0,
    )
    db.add(user)

    if req.is_filmmaker:
        fm = FilmmakerProfile(id=str(uuid.uuid4()), user_id=user.id, bio=req.bio)
        db.add(fm)

    await db.commit()
    await send_verification(user)
    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


class VerifyRequest(BaseModel):
    token: str


@router.post("/verify-email")
async def verify_email(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    """The link from the confirmation email. Confirms the address and pays out anything held for it."""
    try:
        claims = jwt.decode(req.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(400, "This link is invalid or has expired. Ask for a new one.")
    if claims.get("typ") != VERIFY_TYP:
        raise HTTPException(400, "This link is invalid or has expired. Ask for a new one.")
    user = await db.get(User, claims.get("sub"))
    if not user or user.email.lower() != claims.get("email"):
        raise HTTPException(400, "This link is for an email address that's no longer on the account.")
    user.is_verified = True
    await db.commit()
    from app.services.splits import claim_held
    claimed = await claim_held(db, user)
    return {"verified": True, "claimed_credits": claimed}


@router.post("/verify-email/resend", status_code=202)
async def resend_verification(user: User = Depends(get_current_user)):
    if not user.is_verified:
        await send_verification(user)
    return {"sent": not user.is_verified}


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)
