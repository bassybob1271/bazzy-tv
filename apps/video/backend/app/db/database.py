"""Bazzy Video — Database session management"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import os

# Local preview without Postgres: opt in with USE_SQLITE=1 (start-backend.sh sets it).
# Off by default so Docker/production always use DATABASE_URL.
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql") and os.environ.get("USE_SQLITE", "0") == "1":
    _db_url = "sqlite+aiosqlite:///./bazzy_preview.db"

_kwargs = {}
if _db_url.startswith("postgresql"):
    _kwargs = {"pool_size": 20, "max_overflow": 10, "pool_pre_ping": True}

engine = create_async_engine(
    _db_url,
    echo=settings.DEBUG,
    **_kwargs,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
