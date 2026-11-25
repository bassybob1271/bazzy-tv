"""Bazzy Video — Auth routes"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.db.database import get_db
from app.models.models import User, UserRole, FilmmakerProfile
from app.core.security import hash_password, verify_password, create_access_token
import uuid

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
    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)
