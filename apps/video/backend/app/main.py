"""Bazzy Video — FastAPI Application Entry Point"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.database import engine, Base
from app.seed import seed_demo_catalog
from app.api.routes import auth, titles, wallet, filmmaker, admin
import structlog, os

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # pg_advisory_xact_lock is PostgreSQL-only; skip on SQLite
        if str(engine.url).startswith("postgresql"):
            from sqlalchemy import text
            await conn.execute(text("SELECT pg_advisory_xact_lock(4242001)"))
            # create_all doesn't alter existing enum types: add categories
            # introduced after the database was first created.
            await conn.execute(text("""
                DO $$ BEGIN
                  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contentcategory') THEN
                    ALTER TYPE contentcategory ADD VALUE IF NOT EXISTS 'COMEDY';
                  END IF;
                END $$;
            """))
        await conn.run_sync(Base.metadata.create_all)
    await seed_demo_catalog()
    logger.info("bazzy_video.startup", version=settings.APP_VERSION)
    yield
    await engine.dispose()
    logger.info("bazzy_video.shutdown")


app = FastAPI(
    title="Bazzy Video API",
    description="Full-stack cooperative video distribution platform API",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(auth.router,       prefix="/api/v1")
app.include_router(titles.router,     prefix="/api/v1")
app.include_router(wallet.router,     prefix="/api/v1")
app.include_router(filmmaker.router,  prefix="/api/v1")
app.include_router(admin.router,      prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
