"""Bazzy Live — demo shows on the shared Bazzy TV backend.

Runs at API startup when SEED_DEMO=true (or by default in SQLite preview mode)
and any demo show (matched by slug) is missing. Safe to leave on: it only
adds missing demo shows and never changes or removes existing ones.

UPCOMING: the seven Greenhouse BK posters (apps/live/web/public/posters/) shown in
the home slider. Dates were moved to after Nov 25, 2026 so they're upcoming.
PREVIOUS: placeholder replays for the "Previous Livestreams" rails.

Demo logins (password for all: bazzydemo), shared with the film demo:
  demo@bazzy.tv             viewer, 5,000 credits (films and shows, one wallet)
  greenhouse-demo@bazzy.tv  the Greenhouse BK artist account that "owns" the demo shows
  admin@bazzy.tv            admin
"""
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, text

from app.core.security import hash_password
from app.db.database import AsyncSessionLocal, engine
from app.models.models import (
    Title, User, UserRole, FilmmakerProfile, ContentCategory, ContentStatus, LiveState,
)

logger = structlog.get_logger()

DEMO_PASSWORD = "bazzydemo"

STREAM_A = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"
STREAM_B = "https://devstreaming-cdn.apple.com/videos/streaming/examples/img_bipbop_adv_example_fmp4/master.m3u8"

GREENHOUSE = "Greenhouse BK, 1271A Fulton St, Brooklyn NY"
ET = timezone(timedelta(hours=-5))  # New York, winter

# (title, performers, category, start (ET), poster file, synopsis)
UPCOMING = [
    ("Garden — Album Release Show", "Kevin Holliday", "album_releases",
     datetime(2026, 12, 4, 20, 0, tzinfo=ET), "kevin-holliday-garden.jpg",
     "Kevin Holliday celebrates the release of Garden with a full live set at the Greenhouse."),
    ("Feels — Listening Experience", "IRRELEGANCE", "listening",
     datetime(2026, 12, 9, 20, 0, tzinfo=ET), "feels-listening-experience.jpg",
     "IRRELEGANCE plays Feels front to back: a listening experience, lights low, sound up."),
    ("Nava Drops — Album Release Event", "Nava Drops with Treyzis & Rajah Sound", "album_releases",
     datetime(2026, 12, 12, 19, 0, tzinfo=ET), "nava-drops-album-release.jpg",
     "Nava Drops releases the new album live, with Treyzis and Rajah Sound."),
    ("Mono 222 — NYC Premiere", "Mono 222", "screenings",
     datetime(2026, 12, 15, 19, 0, tzinfo=ET), "mono-222-premiere.jpg",
     "The New York premiere of Mono 222: screening plus party, streamed from greenhouse bk."),
    ("Sweata — A Cozy Night in Brooklyn", "Sweata + special guests", "concerts",
     datetime(2026, 12, 17, 20, 0, tzinfo=ET), "sweata-cozy-night.jpg",
     "Sweata brings A Cozy Night in Brooklyn to the Greenhouse, with special guests."),
    ("Laney Tripp, Avery Friedman, Nora Stanley & Coco Smith", "Laney Tripp · Avery Friedman · Nora Stanley · Coco Smith", "concerts",
     datetime(2026, 12, 19, 19, 30, tzinfo=ET), "greenhouse-four-voices.jpg",
     "Four artists, one bill. Doors 7 PM, show 7:30 PM."),
    ("VPC Ensemble — Release Ritual", "VPC Ensemble with Surya Botofasina, A Space for Sound & Julie Hill", "sound_baths",
     datetime(2026, 12, 21, 18, 0, tzinfo=ET), "vpc-release-ritual.jpg",
     "A sound bath meditation and concert celebrating Life Is a Strange Loop."),
]

# (title, performers, category, days ago, synopsis) — placeholder replays
PREVIOUS = [
    ("Fulton Street Folk Night", "The Greenhouse Songwriters", "concerts", 6,
     "Five songwriters, one microphone, an hour of new songs."),
    ("Brass in the Greenhouse", "Bed-Stuy Brass Collective", "concerts", 20,
     "A ten-piece brass band takes over the room."),
    ("Late Set: Bedford Avenue Trio", "Bedford Avenue Trio", "concerts", 41,
     "Piano, bass and drums, after midnight."),
    ("Basement Tapes — Release Party", "Low Ceiling", "album_releases", 13,
     "Low Ceiling plays their debut record live for the first time."),
    ("First Spin: Summer EP", "Marisol Vey", "album_releases", 55,
     "Marisol Vey premieres her summer EP with a full band."),
    ("Vinyl Only: Deep Cuts", "DJ Crate Theory", "listening", 9,
     "A listening room built around records nobody else plays."),
    ("Producer Playback Night", "Greenhouse Producers Circle", "listening", 34,
     "Six producers play unreleased beats and talk through how they made them."),
    ("Shorts at the Greenhouse", "Brooklyn Shorts Club", "screenings", 16,
     "Eight short films from Brooklyn directors, with a Q&A after."),
    ("Doc Night: Made in Bed-Stuy", "Fulton Films", "screenings", 48,
     "A documentary about the shops, kitchens and studios of Fulton Street."),
    ("New Moon Sound Bath", "A Space for Sound", "sound_baths", 3,
     "Crystal bowls, gongs and an hour of quiet."),
    ("Gong & Strings Evening Ritual", "Julie Hill", "sound_baths", 27,
     "Gongs, cello and voice for the end of the week."),
]


def _slug(s: str) -> str:
    return re.sub(r"-+", "-", "".join(c if c.isalnum() else "-" for c in s.lower().replace("'", ""))).strip("-")


async def seed_live_shows() -> None:
    # Seed by default in SQLite (preview) mode, or when SEED_DEMO=true
    is_sqlite = str(engine.url).startswith("sqlite")
    seed_env = os.getenv("SEED_DEMO", "").lower()
    if not is_sqlite and seed_env not in ("1", "true", "yes"):
        return

    all_slugs = [_slug(r[0]) for r in UPCOMING + PREVIOUS]
    async with AsyncSessionLocal() as db:
        if not is_sqlite:
            # Several API workers start at once: let one seed at a time.
            # Held until this session's transaction commits or rolls back.
            await db.execute(text("SELECT pg_advisory_xact_lock(4242003)"))
        existing_slugs = set((await db.execute(select(Title.slug))).scalars())
        if all(sl in existing_slugs for sl in all_slugs):
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
        artist = await get_or_create_user("greenhouse-demo@bazzy.tv", "Greenhouse BK", UserRole.FILMMAKER)
        await db.flush()

        fm = (await db.execute(
            select(FilmmakerProfile).where(FilmmakerProfile.user_id == artist.id)
        )).scalar_one_or_none()
        if not fm:
            fm = FilmmakerProfile(id=str(uuid.uuid4()), user_id=artist.id,
                                  bio="Greenhouse BK, the live room at LDStudios, Brooklyn (demo account).")
            db.add(fm)
            await db.flush()

        def show(**kw) -> Title:
            return Title(
                id=str(uuid.uuid4()), filmmaker_id=fm.id, venue=GREENHOUSE,
                rating="PG", language="en", drm_enabled=False,
                rent_credits=200, buy_credits=800, is_free=False,
                playback_id=secrets.token_hex(8), stream_key=secrets.token_urlsafe(24),
                status=ContentStatus.LIVE, **kw,
            )

        added = 0
        for i, (name, who, cat, start, poster, synopsis) in enumerate(UPCOMING):
            slug = _slug(name)
            if slug in existing_slugs:
                continue
            db.add(show(
                title=name, slug=slug, synopsis=synopsis, performer_name=who,
                category=ContentCategory(cat), year=start.year, starts_at=start,
                tags=[cat, "brooklyn", "greenhouse"],
                poster_url=f"/posters/{poster}",
                live_state=LiveState.SCHEDULED, published_at=now,
                editorial_score=0.9 - i * 0.05,
            ))
            added += 1

        for i, (name, who, cat, days_ago, synopsis) in enumerate(PREVIOUS):
            slug = _slug(name)
            if slug in existing_slugs:
                continue
            start = (now - timedelta(days=days_ago)).replace(hour=1, minute=0, second=0, microsecond=0)
            views = 900 + (len(PREVIOUS) - i) * 310
            db.add(show(
                title=name, slug=slug, synopsis=synopsis, performer_name=who,
                category=ContentCategory(cat), year=start.year, runtime_minutes=60 + (i % 4) * 15,
                tags=[cat, "brooklyn", "greenhouse", "replay"],
                poster_url=f"https://picsum.photos/seed/bazzylive-{slug}/600/900",
                hls_manifest_url=STREAM_A if i % 2 == 0 else STREAM_B,
                starts_at=start, ended_at=start + timedelta(hours=2),
                live_state=LiveState.ENDED, published_at=start,
                view_count=views, completion_rate=round(0.55 + (i % 5) * 0.07, 3),
                fan_vote_score=round(0.7 + (i % 4) * 0.06, 3),
                revenue_velocity=float(views // 10),
            ))
            added += 1

        await db.commit()
        logger.info("bazzy_live.demo_seeded", shows=added)
