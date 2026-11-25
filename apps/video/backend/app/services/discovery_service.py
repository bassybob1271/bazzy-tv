"""Bazzy Video — Discovery & Recommendation Engine
Signal weights:
  35% completion rate
  20% Fan Unit cooperative votes
  20% credit revenue velocity (7-day)
  15% editorial score (human curation)
  10% social referral conversion
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from app.models.models import Title, ContentCategory, ContentStatus, FanVote
from app.core.config import settings
from typing import Optional, List
import re


class DiscoveryService:

    # ── Algorithm weights ─────────────────────────────────────────────────────
    W_COMPLETION  = 0.35
    W_FAN_VOTES   = 0.20
    W_REVENUE     = 0.20
    W_EDITORIAL   = 0.15
    W_SOCIAL      = 0.10

    def _compute_score(self, title: Title) -> float:
        """Composite discovery score (0–100)."""
        return (
            (title.completion_rate * 100)       * self.W_COMPLETION +
            (title.fan_vote_score * 20)          * self.W_FAN_VOTES +
            (min(title.revenue_velocity, 1000) / 10) * self.W_REVENUE +
            (title.editorial_score * 100)        * self.W_EDITORIAL
        )

    # ── Home rails ────────────────────────────────────────────────────────────

    async def get_home_rails(self, db: AsyncSession, user_id: Optional[str] = None):
        """Return all home page rails."""
        return {
            "hero":           await self.get_editorial_picks(db, limit=5),
            "trending":       await self.get_trending(db, limit=20),
            "new_arrivals":   await self.get_new_arrivals(db, limit=20),
            "documentary":    await self.get_by_category(db, ContentCategory.DOCUMENTARY, 20),
            "romance":        await self.get_by_category(db, ContentCategory.ROMANCE, 20),
            "crime":          await self.get_by_category(db, ContentCategory.CRIME, 20),
            "horror":         await self.get_by_category(db, ContentCategory.HORROR, 20),
            "new_releases":   await self.get_by_category(db, ContentCategory.NEW_RELEASES, 20),
            "fan_picks":      await self.get_fan_picks(db, limit=20),
        }

    async def get_trending(self, db: AsyncSession, limit: int = 20) -> List[Title]:
        result = await db.execute(
            select(Title)
            .where(Title.status == ContentStatus.LIVE)
            .order_by(desc(Title.revenue_velocity), desc(Title.view_count))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_editorial_picks(self, db: AsyncSession, limit: int = 10) -> List[Title]:
        result = await db.execute(
            select(Title)
            .where(Title.status == ContentStatus.LIVE, Title.editorial_score > 0.5)
            .order_by(desc(Title.editorial_score))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_fan_picks(self, db: AsyncSession, limit: int = 20) -> List[Title]:
        result = await db.execute(
            select(Title)
            .where(Title.status == ContentStatus.LIVE)
            .order_by(desc(Title.fan_vote_score))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_new_arrivals(self, db: AsyncSession, limit: int = 20) -> List[Title]:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=90)
        result = await db.execute(
            select(Title)
            .where(Title.status == ContentStatus.LIVE, Title.published_at >= cutoff)
            .order_by(desc(Title.published_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def get_by_category(self, db: AsyncSession,
                               category: ContentCategory, limit: int = 20) -> List[Title]:
        result = await db.execute(
            select(Title)
            .where(Title.status == ContentStatus.LIVE, Title.category == category)
            .order_by(desc(Title.completion_rate), desc(Title.fan_vote_score))
            .limit(limit)
        )
        return result.scalars().all()

    # ── Mood-based natural language discovery ─────────────────────────────────

    MOOD_MAP = {
        # (categories, min_runtime, max_runtime, sort_by_editorial)
        "intense":     ([ContentCategory.CRIME, ContentCategory.HORROR], 80, None, False),
        "thriller":    ([ContentCategory.CRIME], 70, None, False),
        "scary":       ([ContentCategory.HORROR], None, None, False),
        "funny":       ([ContentCategory.ROMANCE], None, 100, True),
        "date night":  ([ContentCategory.ROMANCE], None, 120, True),
        "romantic":    ([ContentCategory.ROMANCE], None, None, True),
        "learn":       ([ContentCategory.DOCUMENTARY], None, None, True),
        "documentary": ([ContentCategory.DOCUMENTARY], None, None, False),
        "true crime":  ([ContentCategory.CRIME, ContentCategory.DOCUMENTARY], None, None, False),
        "new":         ([ContentCategory.NEW_RELEASES], None, None, False),
        "short":       (None, None, 40, True),
        "quick":       (None, None, 40, True),
        "weird":       (None, None, None, True),
    }

    async def mood_query(self, db: AsyncSession, query: str, limit: int = 20) -> List[Title]:
        """Natural language mood-based query → list of titles."""
        q_lower = query.lower()
        matched_mood = None
        for keyword, params in self.MOOD_MAP.items():
            if keyword in q_lower:
                matched_mood = params
                break

        stmt = select(Title).where(Title.status == ContentStatus.LIVE)

        if matched_mood:
            categories, min_rt, max_rt, editorial = matched_mood
            if categories:
                stmt = stmt.where(Title.category.in_(categories))
            if min_rt:
                stmt = stmt.where(Title.runtime_minutes >= min_rt)
            if max_rt:
                stmt = stmt.where(Title.runtime_minutes <= max_rt)
            if editorial:
                stmt = stmt.order_by(desc(Title.editorial_score), desc(Title.fan_vote_score))
            else:
                stmt = stmt.order_by(desc(Title.completion_rate), desc(Title.revenue_velocity))
        else:
            # Fallback: full-text match on title/synopsis + algo score
            stmt = stmt.where(
                or_(
                    Title.title.ilike(f"%{query}%"),
                    Title.synopsis.ilike(f"%{query}%"),
                )
            ).order_by(desc(Title.completion_rate))

        result = await db.execute(stmt.limit(limit))
        return result.scalars().all()

    # ── Because-you-watched (collaborative) ───────────────────────────────────

    async def because_you_watched(self, db: AsyncSession, title_id: str,
                                   limit: int = 10) -> List[Title]:
        """Find titles in the same category with similar completion profile."""
        result = await db.execute(select(Title).where(Title.id == title_id))
        source = result.scalar_one_or_none()
        if not source:
            return []

        result2 = await db.execute(
            select(Title)
            .where(
                Title.status == ContentStatus.LIVE,
                Title.category == source.category,
                Title.id != title_id,
                Title.completion_rate >= max(0, source.completion_rate - 0.2),
            )
            .order_by(desc(Title.fan_vote_score))
            .limit(limit)
        )
        return result2.scalars().all()

    # ── Fan vote ──────────────────────────────────────────────────────────────

    async def submit_fan_vote(self, db: AsyncSession, user_id: str,
                               title_id: str, vote: int):
        """Submit 1–5 star vote. Updates title fan_vote_score."""
        if not 1 <= vote <= 5:
            from fastapi import HTTPException
            raise HTTPException(400, "Vote must be 1–5")

        # Upsert vote
        existing = await db.execute(
            select(FanVote).where(FanVote.user_id == user_id, FanVote.title_id == title_id)
        )
        fan_vote = existing.scalar_one_or_none()
        if fan_vote:
            fan_vote.vote = vote
        else:
            import uuid
            db.add(FanVote(id=str(uuid.uuid4()), user_id=user_id, title_id=title_id, vote=vote))

        # Recompute avg for title
        avg_result = await db.execute(
            select(func.avg(FanVote.vote)).where(FanVote.title_id == title_id)
        )
        avg_vote = avg_result.scalar() or 0
        from sqlalchemy import update
        await db.execute(
            update(Title).where(Title.id == title_id)
            .values(fan_vote_score=avg_vote / 5.0)
        )
        await db.commit()
