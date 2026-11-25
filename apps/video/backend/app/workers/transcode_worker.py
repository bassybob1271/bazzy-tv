"""Bazzy Video — Celery transcode worker"""
from celery import Celery
from app.core.config import settings

celery_app = Celery("bazzy_video", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_default_queue="default",   # worker listens on transcode,default
    task_soft_time_limit=3600,   # 1hr — large files
    task_time_limit=7200,
)


@celery_app.task(bind=True, name="transcode_title", max_retries=3)
def transcode_title(self, title_id: str, master_path: str):
    """Async transcode task. Runs on OCI GPU compute worker."""
    import asyncio
    from app.services.transcode_service import TranscodeService
    from app.db.database import AsyncSessionLocal

    async def _run():
        async with AsyncSessionLocal() as db:
            svc = TranscodeService()
            hls_url = await svc.ingest_and_transcode(db, title_id, master_path)
            return hls_url

    try:
        loop = asyncio.get_event_loop()
        hls_url = loop.run_until_complete(_run())
        return {"title_id": title_id, "hls_url": hls_url, "status": "complete"}
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="compute_algo_scores")
def compute_algo_scores():
    """Nightly job: recompute completion rates + revenue velocity for all titles."""
    import asyncio
    from app.db.database import AsyncSessionLocal
    from app.models.models import Title, ViewingHistory
    from sqlalchemy import select, update, func
    from datetime import datetime, timedelta

    async def _run():
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Title).where(Title.status == "live"))
            titles = result.scalars().all()

            week_ago = datetime.utcnow() - timedelta(days=7)

            for title in titles:
                # Completion rate: avg of (watch_position / runtime)
                view_result = await db.execute(
                    select(func.avg(ViewingHistory.watch_position_s))
                    .where(ViewingHistory.title_id == title.id)
                )
                avg_watch_s = view_result.scalar() or 0
                runtime_s = (title.runtime_minutes or 1) * 60
                completion = min(1.0, avg_watch_s / runtime_s)

                # Revenue velocity: credits in last 7 days
                from app.models.models import CreditTransaction
                vel_result = await db.execute(
                    select(func.sum(func.abs(CreditTransaction.credits_delta)))
                    .where(
                        CreditTransaction.title_id == title.id,
                        CreditTransaction.created_at >= week_ago,
                    )
                )
                velocity = vel_result.scalar() or 0

                await db.execute(
                    update(Title).where(Title.id == title.id)
                    .values(completion_rate=completion, revenue_velocity=float(velocity))
                )
            await db.commit()

    asyncio.get_event_loop().run_until_complete(_run())


# Schedule nightly score computation
celery_app.conf.beat_schedule = {
    "nightly-algo-scores": {
        "task": "compute_algo_scores",
        "schedule": 86400,  # 24 hours
    },
}
