"""Bazzy Video — demo catalog seed.

Runs at API startup when SEED_DEMO=true (or by default in SQLite preview mode)
and any demo title (matched by slug) is missing. Safe to leave on: it only
adds missing demo titles and never changes or removes existing ones.

Demo logins (password for all: bazzydemo):
  demo@bazzy.tv       viewer, 5,000 credits
  filmmaker@bazzy.tv  filmmaker who "owns" the demo catalog
  admin@bazzy.tv      admin
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal, engine
from app.models.models import (
    Title, User, UserRole, FilmmakerProfile, ContentCategory, ContentStatus,
)

logger = structlog.get_logger()

DEMO_PASSWORD = "bazzydemo"

STREAM_A = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
STREAM_B = "https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8"

CATALOG = [
    ("Second Line Sunday", "documentary", 2026, 84, True, 0.95, 0.92, 18420,
     "A year inside New Orleans' social aid & pleasure clubs, following the brass bands, the dancers and the families who keep the parade alive."),
    ("Frenchmen Street", "romance", 2025, 102, False, 0.90, 0.88, 12310,
     "A touring trumpet player and a bartender on Frenchmen Street get one week before the band leaves town."),
    ("Bayou After Dark", "horror", 2026, 91, False, 0.85, 0.81, 9875,
     "Three friends take a night swamp tour off the map. The guide never comes back to the boat."),
    ("The Ninth Ward Ledger", "crime", 2025, 112, False, 0.80, 0.86, 11204,
     "A retired detective reopens a 2005 case when a ledger surfaces in a flood-damaged church."),
    ("Sound of the Crescent", "documentary", 2024, 76, True, 0.70, 0.90, 21033,
     "From Congo Square to bounce: three centuries of New Orleans music told by the people who made it."),
    ("Last Call at Tipitina's", "new_releases", 2026, 97, False, 0.75, 0.79, 4310,
     "A club owner has one night to save her venue from a developer — and a lineup of musicians who all owe her a favor."),
    ("Magnolia & Mercy", "romance", 2026, 95, False, 0.40, 0.77, 6120,
     "Two rival wedding planners in the Garden District are forced to co-plan the wedding of the year."),
    ("Cold Case Carnival", "crime", 2026, 104, False, 0.45, 0.74, 5402,
     "A Mardi Gras float builder becomes the prime suspect when a krewe captain disappears."),
    ("The Lantern Keeper", "horror", 2025, 88, False, 0.35, 0.72, 7788,
     "A lighthouse keeper on Lake Pontchartrain starts receiving signals from a ship that sank in 1931."),
    ("Studio Rats", "documentary", 2026, 68, True, 0.60, 0.84, 8930,
     "Inside the late-night sessions of New Orleans producers building records in bedrooms, garages and borrowed studios."),
    ("Streetcar Nights", "new_releases", 2026, 89, False, 0.55, 0.70, 3120,
     "An anthology of five strangers, five stops and one long ride down St. Charles Avenue."),
    ("Paper Krewe", "new_releases", 2026, 81, True, 0.30, 0.68, 2201,
     "A crew of art students builds a guerrilla Mardi Gras parade out of cardboard — and accidentally starts a movement."),
    ("Second Liners Anonymous", "comedy", 2026, 93, False, 0.50, 0.80, 6480,
     "A support group for people who can't stop following parades meets every Sunday — right on the parade route."),
    ("Beignets for Breakfast", "comedy", 2025, 86, True, 0.25, 0.76, 4875,
     "Two feuding cousins inherit a French Quarter café and have one Jazz Fest weekend to prove who should run it."),
]


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower().replace("'", "")).strip("-").replace("--", "-")


async def seed_demo_catalog() -> None:
    # Seed by default in SQLite (preview) mode, or when SEED_DEMO=true
    is_sqlite = str(engine.url).startswith("sqlite")
    seed_env = os.getenv("SEED_DEMO", "").lower()
    if not is_sqlite and seed_env not in ("1", "true", "yes"):
        return

    async with AsyncSessionLocal() as db:
        if not is_sqlite:
            # Several API workers start at once: let one seed at a time.
            # Held until this session's transaction commits or rolls back.
            await db.execute(text("SELECT pg_advisory_xact_lock(4242002)"))
        # Add any demo titles that are missing (by slug), so titles added to
        # CATALOG later also reach databases seeded by an earlier version.
        existing_slugs = set((await db.execute(select(Title.slug))).scalars())
        if all(_slug(row[0]) in existing_slugs for row in CATALOG):
            return  # already seeded

        now = datetime.now(timezone.utc)

        async def get_or_create_user(email, name, role, credits=0):
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                return existing
            u = User(id=str(uuid.uuid4()), email=email,
                     hashed_password=hash_password(DEMO_PASSWORD),
                     display_name=name, role=role, credit_balance=credits)
            db.add(u)
            return u

        await get_or_create_user("demo@bazzy.tv", "Demo Viewer", UserRole.VIEWER, credits=5000)
        await get_or_create_user("admin@bazzy.tv", "Bazzy Admin", UserRole.ADMIN)
        fm_user = await get_or_create_user("filmmaker@bazzy.tv", "Crescent City Films", UserRole.FILMMAKER)
        await db.flush()

        fm = (await db.execute(
            select(FilmmakerProfile).where(FilmmakerProfile.user_id == fm_user.id)
        )).scalar_one_or_none()
        if not fm:
            fm = FilmmakerProfile(id=str(uuid.uuid4()), user_id=fm_user.id,
                                  bio="Independent New Orleans production company (demo account).")
            db.add(fm)
            await db.flush()

        for i, (name, cat, year, runtime, free, editorial, fan, views, synopsis) in enumerate(CATALOG):
            slug = _slug(name)
            if slug in existing_slugs:
                continue
            db.add(Title(
                id=str(uuid.uuid4()), filmmaker_id=fm.id,
                title=name, slug=slug, synopsis=synopsis,
                category=ContentCategory(cat), year=year,
                runtime_minutes=runtime, rating="PG",
                tags=[cat, "new orleans"], is_free=free,
                rent_credits=0 if free else 200,
                buy_credits=0 if free else 800,
                poster_url=f"https://picsum.photos/seed/{slug}/600/900",
                hls_manifest_url=STREAM_A if i % 2 == 0 else STREAM_B,
                drm_enabled=False, status=ContentStatus.LIVE,
                published_at=now - timedelta(days=i * 3),
                view_count=views,
                completion_rate=round(0.55 + fan * 0.4, 3),
                fan_vote_score=fan, editorial_score=editorial,
                revenue_velocity=float(views // 10),
            ))
        await db.commit()
        logger.info("bazzy_video.demo_seeded",
                    titles=sum(_slug(r[0]) not in existing_slugs for r in CATALOG))
