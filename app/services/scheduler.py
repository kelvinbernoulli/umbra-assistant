from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.services.ingestion.retry import run_retry_worker

logger = get_logger(__name__)


async def retry_failed_jobs() -> None:
    result = await run_retry_worker(SessionLocal, limit=settings.RETRY_BATCH_LIMIT)
    logger.info(
        "Scheduled ingestion retry completed | selected=%s succeeded=%s failed=%s",
        result["selected"],
        result["succeeded"],
        result["failed"],
    )


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        retry_failed_jobs,
        trigger="interval",
        seconds=settings.RETRY_INTERVAL_SECONDS,
        id="retry-failed-ingestion",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=settings.RETRY_INTERVAL_SECONDS,
    )
    return scheduler