"""
tests/test_integration.py — End-to-end integration tests for the job ingestion pipeline.
"""

import os
from datetime import datetime, timezone
import pytest
import respx
import httpx
from sqlalchemy import select

from adapters.remotive_rss import RemotiveRSSAdapter
from pipeline.runner import run_pipeline
from pipeline.circuit_breaker import STATE_CLOSED, STATE_OPEN, STATE_HALF_OPEN, get_or_create_health
from models import Job, IngestionRun, AdapterHealth


def read_fixture(filename: str) -> bytes:
    fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", filename)
    with open(fixture_path, "rb") as f:
        return f.read()


async def test_successful_e2e_double_ingestion(db_session, respx_mock):
    """
    Validates that a real pipeline execution with mock HTTP input successfully parses,
    normalizes, deduplicates, and persists data to PostgreSQL, and that running it
    a second time deduplicates all items without multiplying records.
    """
    # 1. Mock external Remotive HTTP endpoint
    rss_url = "https://remotive.com/remote-jobs/feed"
    valid_xml = read_fixture("remotive/valid_feed.xml")
    respx_mock.get(rss_url).mock(return_value=httpx.Response(200, content=valid_xml))

    adapter = RemotiveRSSAdapter()

    # --- RUN 1 ---
    result1 = await run_pipeline(adapter, db_session)
    assert result1.status == "success"
    assert result1.fetched_count == 3
    assert result1.parsed_count == 3
    assert result1.new_count == 3
    assert result1.duplicate_count == 0
    assert result1.error_count == 0

    # Verify DB contains the rows
    stmt_jobs = select(Job).order_by(Job.id)
    jobs_res = await db_session.execute(stmt_jobs)
    jobs = jobs_res.scalars().all()
    assert len(jobs) == 3
    
    # Assert normalized values match fixture details
    assert jobs[0].title == "Senior Python Engineer"
    assert jobs[0].company == "Acdyon Corp"
    assert jobs[0].location == "Remote"
    assert jobs[0].category == "Software Development"
    assert jobs[0].source == "remotive"
    
    assert jobs[1].title == "React Developer"
    assert jobs[1].company == "Vercel Ltd"

    # Verify IngestionRun saved
    stmt_runs = select(IngestionRun).where(IngestionRun.run_id == result1.run_id)
    run_res = await db_session.execute(stmt_runs)
    run_rec = run_res.scalar_one_or_none()
    assert run_rec is not None
    assert run_rec.status == "success"
    assert run_rec.new_count == 3

    # Commit database transaction to release lock/active state before RUN 2
    await db_session.commit()

    # --- RUN 2 ---
    result2 = await run_pipeline(adapter, db_session)
    assert result2.status == "success"
    assert result2.fetched_count == 3
    assert result2.parsed_count == 3
    assert result2.new_count == 0
    assert result2.duplicate_count == 3  # All existing jobs
    assert result2.error_count == 0

    # Verify database still contains exactly 3 jobs
    jobs_res2 = await db_session.execute(stmt_jobs)
    jobs2 = jobs_res2.scalars().all()
    assert len(jobs2) == 3


async def test_failure_integration_http_500(db_session, respx_mock):
    """
    HTTP 500 failures should cause the pipeline to fail and increment the circuit failure count.
    """
    rss_url = "https://remotive.com/remote-jobs/feed"
    respx_mock.get(rss_url).mock(return_value=httpx.Response(500))

    adapter = RemotiveRSSAdapter()

    with pytest.raises(Exception):
        await run_pipeline(adapter, db_session)

    await db_session.rollback()

    # Telemetry should be saved in DB even after exception
    stmt_runs = select(IngestionRun).order_by(IngestionRun.id.desc())
    run_res = await db_session.execute(stmt_runs)
    latest_run = run_res.scalars().first()
    assert latest_run is not None
    assert latest_run.status == "failed"

    # Circuit health check consecutive failures should increment
    health = await get_or_create_health(db_session, "remotive")
    assert health.consecutive_failures == 1


async def test_failure_integration_timeout(db_session, respx_mock):
    """
    HTTP connection timeouts should cause the pipeline to fail and update circuit status.
    """
    rss_url = "https://remotive.com/remote-jobs/feed"
    respx_mock.get(rss_url).mock(side_effect=httpx.ConnectTimeout("Connection timeout"))

    adapter = RemotiveRSSAdapter()

    with pytest.raises(Exception):
        await run_pipeline(adapter, db_session)

    await db_session.rollback()

    # Circuit health check consecutive failures should increment
    health = await get_or_create_health(db_session, "remotive")
    assert health.consecutive_failures == 1


async def test_failure_integration_malformed_records(db_session, respx_mock):
    """
    Malformed feed records are skipped and count as errors. Valid ones are saved.
    The circuit must NOT incorrectly trip for individual record validation issues.
    """
    rss_url = "https://remotive.com/remote-jobs/feed"
    malformed_xml = read_fixture("remotive/malformed_feed.xml")
    respx_mock.get(rss_url).mock(return_value=httpx.Response(200, content=malformed_xml))

    adapter = RemotiveRSSAdapter()
    result = await run_pipeline(adapter, db_session)

    assert result.status == "partial"
    assert result.fetched_count == 1
    assert result.parsed_count == 1
    assert result.new_count == 0
    assert result.error_count == 1
    assert any("at least a non-empty title or a non-empty url" in err for err in result.error_messages)

    # Circuit failures should remain 0 because it was a parsing/validation issue, not a feed connection issue
    health = await get_or_create_health(db_session, "remotive")
    assert health.consecutive_failures == 0


async def test_failure_integration_empty_feed(db_session, respx_mock):
    """
    An empty feed completes successfully with zero jobs, leaving existing jobs intact.
    """
    # Pre-populate 1 job
    existing_job = Job(external_id="pre-ext-1", title="Pre job", source="remotive")
    db_session.add(existing_job)
    await db_session.commit()

    rss_url = "https://remotive.com/remote-jobs/feed"
    empty_xml = read_fixture("remotive/empty_feed.xml")
    respx_mock.get(rss_url).mock(return_value=httpx.Response(200, content=empty_xml))

    adapter = RemotiveRSSAdapter()
    result = await run_pipeline(adapter, db_session)

    assert result.status == "success"
    assert result.fetched_count == 0
    assert result.new_count == 0

    # Existing jobs must be preserved
    stmt_jobs = select(Job)
    jobs_res = await db_session.execute(stmt_jobs)
    jobs = jobs_res.scalars().all()
    assert len(jobs) == 1
    assert jobs[0].title == "Pre job"


async def test_failure_integration_duplicate_feed(db_session, respx_mock):
    """
    Incoming batch containing duplicate rows inside parses successfully,
    persists only 1 job, and logs the duplicate metrics.
    """
    rss_url = "https://remotive.com/remote-jobs/feed"
    dupe_xml = read_fixture("remotive/duplicate_feed.xml")
    respx_mock.get(rss_url).mock(return_value=httpx.Response(200, content=dupe_xml))

    adapter = RemotiveRSSAdapter()
    result = await run_pipeline(adapter, db_session)

    assert result.status == "success"
    assert result.fetched_count == 2
    assert result.new_count == 1
    assert result.duplicate_count == 1

    # Verify only 1 row is saved
    stmt_jobs = select(Job)
    jobs_res = await db_session.execute(stmt_jobs)
    jobs = jobs_res.scalars().all()
    assert len(jobs) == 1


async def test_failure_integration_circuit_open(db_session, respx_mock):
    """
    When the circuit breaker is OPEN, executing the pipeline must immediately skip,
    bypass the HTTP mock entirely, and persist a 'skipped' IngestionRun record.
    """
    # 1. Set circuit breaker state to OPEN manually in database health
    health = await get_or_create_health(db_session, "remotive")
    health.circuit_state = STATE_OPEN
    health.circuit_opened_at = datetime.now(timezone.utc)
    health.consecutive_failures = 5
    await db_session.commit()

    # Define an HTTP mock that raises an assertion error if called
    rss_url = "https://remotive.com/remote-jobs/feed"
    route = respx_mock.get(rss_url).mock(side_effect=AssertionError("HTTP client should not have been called!"))

    adapter = RemotiveRSSAdapter()
    result = await run_pipeline(adapter, db_session)

    assert result.status == "skipped"
    assert result.fetched_count == 0
    assert result.new_count == 0
    assert result.error_messages == ["Ingestion skipped: Circuit breaker is OPEN."]

    # Verify HTTP mock was indeed never called
    assert not route.called

    # Verify skipped IngestionRun is persisted
    stmt_runs = select(IngestionRun).where(IngestionRun.run_id == result.run_id)
    run_res = await db_session.execute(stmt_runs)
    run_rec = run_res.scalar_one_or_none()
    assert run_rec is not None
    assert run_rec.status == "skipped"
