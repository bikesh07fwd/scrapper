"""
scheduler.py — periodic background job ingestion scheduler using APScheduler.
"""

import os
from typing import Optional
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from database import AsyncSessionLocal
from adapters.remotive_rss import RemotiveRSSAdapter
from pipeline.runner import run_pipeline

logger = structlog.get_logger(__name__)


async def scheduled_ingestion_job() -> None:
    """
    Background job function executed by APScheduler.
    Uses its own clean database session and triggers the existing runner.
    """
    logger.info("scheduled.ingestion.started", adapter="remotive")
    
    async with AsyncSessionLocal() as session:
        try:
            adapter = RemotiveRSSAdapter()
            result = await run_pipeline(adapter, session)
            logger.info(
                "scheduled.ingestion.completed",
                status=result.status,
                run_id=result.run_id,
                fetched=result.fetched_count,
                new=result.new_count,
                duplicates=result.duplicate_count,
            )
        except Exception as exc:
            # Scheduler exception must NOT crash the FastAPI application.
            # Log structured details and let the next execution run.
            logger.error(
                "scheduled.ingestion.failed",
                adapter="remotive",
                error=str(exc),
            )


def start_scheduler() -> AsyncIOScheduler:
    """
    Initializes, configures, and starts the background AsyncIOScheduler.
    Registers the Remotive ingestion interval job.
    """
    scheduler = AsyncIOScheduler()
    
    interval_sec = os.getenv("INGESTION_INTERVAL_SECONDS")
    
    if interval_sec:
        # Verification / Test mode
        sec_val = int(interval_sec)
        scheduler.add_job(
            scheduled_ingestion_job,
            trigger="interval",
            seconds=sec_val,
            id="remotive-ingestion",
            max_instances=1,
            misfire_grace_time=60,
            replace_existing=True,
        )
        logger.info(
            "scheduler.started.test_mode",
            message=f"Scheduled Remotive ingestion every {sec_val} seconds",
        )
    else:
        # Production mode
        scheduler.add_job(
            scheduled_ingestion_job,
            trigger="interval",
            minutes=settings.remotive_interval_minutes,
            id="remotive-ingestion",
            max_instances=1,
            misfire_grace_time=60,
            replace_existing=True,
        )
        logger.info(
            "scheduler.started.production_mode",
            message=f"Scheduled Remotive ingestion every {settings.remotive_interval_minutes} minutes",
        )
        
    scheduler.start()
    return scheduler


def shutdown_scheduler(scheduler: AsyncIOScheduler) -> None:
    """
    Clean shutdown of the scheduler instance.
    """
    logger.info("scheduler.shutting_down")
    try:
        scheduler.shutdown(wait=False)
        logger.info("scheduler.shutdown_complete")
    except Exception as exc:
        logger.warning("scheduler.shutdown_failed", error=str(exc))
