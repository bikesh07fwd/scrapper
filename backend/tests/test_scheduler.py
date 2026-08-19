"""
tests/test_scheduler.py — Unit and integration tests for the background scheduler.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi.testclient import TestClient

from config import settings
from main import app
from scheduler import (
    start_scheduler,
    shutdown_scheduler,
    scheduled_ingestion_job,
)
from pipeline.runner import RunResult


class AsyncContextManagerMock:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncContextManagerMock())
    return session


def test_scheduler_creation_and_registration():
    """Verifies scheduler is created with default Remotive 30 minutes interval, stable job ID, and correct config."""
    # Ensure env variable is clear
    if "INGESTION_INTERVAL_SECONDS" in os.environ:
        del os.environ["INGESTION_INTERVAL_SECONDS"]

    # Mock settings value
    settings.remotive_interval_minutes = 30

    scheduler = start_scheduler()
    try:
        assert isinstance(scheduler, AsyncIOScheduler)
        assert scheduler.running is True

        # Check job registration
        jobs = scheduler.get_jobs()
        assert len(jobs) == 1
        job = jobs[0]

        assert job.id == "remotive-ingestion"
        assert job.max_instances == 1
        assert job.misfire_grace_time == 60
        
        # Verify interval is 30 minutes
        assert job.trigger.interval.total_seconds() == 30 * 60
    finally:
        shutdown_scheduler(scheduler)


def test_duplicate_registration_does_not_multiply_jobs():
    """start_scheduler replaces the existing job with same ID, preventing duplicate copies."""
    scheduler = start_scheduler()
    try:
        jobs_first = scheduler.get_jobs()
        assert len(jobs_first) == 1

        # Register again on same instance
        scheduler.add_job(
            lambda: None,
            trigger="interval",
            minutes=30,
            id="remotive-ingestion",
            max_instances=1,
            replace_existing=True,
        )
        jobs_second = scheduler.get_jobs()
        # Should still be exactly one job
        assert len(jobs_second) == 1
    finally:
        shutdown_scheduler(scheduler)


def test_lifespan_scheduler_lifecycle():
    """FastAPI TestClient context startup triggers lifespan to start and shutdown the scheduler."""
    # Temporarily force scheduler enabled in config
    original_enabled = settings.scheduler_enabled
    settings.scheduler_enabled = True
    
    with patch("main.start_scheduler") as mock_start, \
         patch("main.shutdown_scheduler") as mock_shutdown:
        
        mock_sched = MagicMock()
        mock_start.return_value = mock_sched

        # TestClient enter/exit triggers the lifespan context manager
        with TestClient(app):
            mock_start.assert_called_once()
            
        mock_shutdown.assert_called_once_with(mock_sched)
    
    settings.scheduler_enabled = original_enabled


@pytest.mark.asyncio
async def test_scheduled_job_calls_runner(mock_db_session):
    """The scheduled job fetches adapter, opens session, and invokes run_pipeline directly."""
    mock_run_result = RunResult(
        run_id="run-sched-1",
        adapter="remotive",
        status="success",
        fetched_count=10,
        parsed_count=10,
        new_count=5,
        duplicate_count=5,
        error_count=0,
        error_messages=[],
        started_at=MagicMock(),
        finished_at=MagicMock(),
    )

    with patch("scheduler.AsyncSessionLocal", return_value=mock_db_session), \
         patch("scheduler.run_pipeline", new_callable=AsyncMock) as mock_run:
        
        mock_run.return_value = mock_run_result

        # Execute scheduled job directly
        await scheduled_ingestion_job()

        # Should invoke runner directly (no trigger cooldown is touched)
        mock_run.assert_called_once()
        args = mock_run.call_args[0]
        # First arg is the Remotive adapter instance
        assert args[0].name == "remotive"


@pytest.mark.asyncio
async def test_scheduler_exception_does_not_crash_app(mock_db_session):
    """If run_pipeline raises an exception, scheduled job logs the error but does not crash process."""
    with patch("scheduler.AsyncSessionLocal", return_value=mock_db_session), \
         patch("scheduler.run_pipeline", side_effect=Exception("Database connection failure")) as mock_run, \
         patch("scheduler.logger") as mock_logger:

        # Triggering ingestion job should NOT raise exception up
        await scheduled_ingestion_job()

        # Logger should record the failure details
        mock_logger.error.assert_called_once_with(
            "scheduled.ingestion.failed",
            adapter="remotive",
            error="Database connection failure",
        )
