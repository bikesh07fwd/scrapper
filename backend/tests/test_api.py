"""
tests/test_api.py — API endpoints unit and integration tests.
"""

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import respx
import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from routers.trigger import CooldownManager, get_cooldown_manager
from database import get_db
from models import Job, IngestionRun, AdapterHealth
from pipeline.runner import RunResult
from pipeline.circuit_breaker import STATE_CLOSED, STATE_OPEN


# Initialize TestClient
client = TestClient(app)


# --- Mock Cooldown Clock Helper ---
class MockClock:
    def __init__(self, current_time: float = 100.0):
        self.current_time = current_time

    def __call__(self) -> float:
        return self.current_time


@pytest.fixture
def mock_clock():
    return MockClock()


class AsyncContextManagerMock:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncContextManagerMock())
    session.execute = AsyncMock()
    return session


# --- Health API Tests ---

def test_health_endpoint_connected(mock_session):
    """If DB connection succeeds, /health returns 200, healthy status, and adapter health."""
    mock_db_res = MagicMock()
    mock_db_res.scalar.return_value = 1
    
    # Second query for AdapterHealth returns a list of health objects
    health_record = AdapterHealth(
        adapter="sandbox",
        circuit_state=STATE_CLOSED,
        consecutive_failures=0,
        last_success_at=datetime.now(timezone.utc),
        last_failure_at=None,
    )
    mock_db_res.scalars.return_value.all.return_value = [health_record]
    
    # Configure mock_session.execute side effects
    mock_session.execute.side_effect = [AsyncMock(), mock_db_res]

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "remotive" in data["adapters"]
        assert "sandbox" in data["adapters"]
        assert data["adapters"]["sandbox"]["state"] == STATE_CLOSED
    finally:
        app.dependency_overrides.clear()


def test_health_endpoint_disconnected(mock_session):
    """If DB connection raises an exception, /health returns 503 Service Unavailable."""
    # Force DB query to raise exception
    mock_session.execute.side_effect = Exception("DB Connection Down")

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
    finally:
        app.dependency_overrides.clear()


# --- Jobs API Tests ---

def test_jobs_list_pagination_and_ordering(mock_session):
    """GET /jobs returns items, total count, limit, offset, and enforces limits."""
    # Mock count query
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 2

    # Mock select items query ordered newest first
    job1 = Job(id=1, title="Job A", company="Corp A", url="http://a", tags='["python"]', published_at=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))
    job2 = Job(id=2, title="Job B", company="Corp B", url="http://b", tags='["react"]', published_at=datetime(2026, 8, 18, 13, 0, tzinfo=timezone.utc))
    
    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [job2, job1]

    mock_session.execute.side_effect = [mock_count_res, mock_items_res]

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/jobs?limit=5&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "Job B"  # ordered newest first
        assert data["items"][0]["tags"] == ["react"]
    finally:
        app.dependency_overrides.clear()


def test_jobs_max_limit_enforced(mock_session):
    """GET /jobs returns 400 Bad Request if limit exceeds 100 or offset < 0."""
    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        # Limit too large
        response = client.get("/jobs?limit=101")
        assert response.status_code == 400
        assert "limit parameter cannot exceed 100" in response.json()["detail"]

        # Negative offset
        response = client.get("/jobs?offset=-1")
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_jobs_detail_success(mock_session):
    """GET /jobs/{id} returns job response if present in database."""
    job = Job(id=42, title="Engineer", company="Corp", url="http://a", tags='["go"]')
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = job
    mock_session.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/jobs/42")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 42
        assert data["title"] == "Engineer"
    finally:
        app.dependency_overrides.clear()


def test_jobs_detail_not_found(mock_session):
    """GET /jobs/{id} returns 404 if record is missing in database."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/jobs/999")
        assert response.status_code == 404
        assert "Job '999' not found" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# --- Ingestion Runs API Tests ---

def test_runs_list_success(mock_session):
    """GET /runs returns paginated IngestionRuns sorted newest first."""
    mock_count_res = MagicMock()
    mock_count_res.scalar.return_value = 1

    run = IngestionRun(
        run_id="run-123",
        adapter="sandbox",
        status="success",
        started_at=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 8, 18, 12, 1, tzinfo=timezone.utc),
        fetched_count=1,
        parsed_count=1,
        new_count=1,
        error_messages='["some_warning"]',
    )
    mock_items_res = MagicMock()
    mock_items_res.scalars.return_value.all.return_value = [run]

    mock_session.execute.side_effect = [mock_count_res, mock_items_res]

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/runs?limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["run_id"] == "run-123"
        assert data["items"][0]["error_messages"] == ["some_warning"]
    finally:
        app.dependency_overrides.clear()


def test_runs_detail_not_found(mock_session):
    """GET /runs/{id} returns 404 if run record does not exist."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_res

    app.dependency_overrides[get_db] = lambda: mock_session
    try:
        response = client.get("/runs/nonexistent-run-id")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# --- Trigger API Tests ---

@respx.mock
async def test_trigger_cooldown_states(mock_session, mock_clock):
    """Verifies that trigger endpoint enforces 60-second trigger cooldown per adapter."""
    # Stub dependencies
    app.dependency_overrides[get_db] = lambda: mock_session
    mock_manager = CooldownManager(clock=mock_clock)
    app.dependency_overrides[get_cooldown_manager] = lambda: mock_manager

    # Mock execution return value
    mock_result = RunResult(
        run_id="run-trigger-1",
        adapter="sandbox",
        status="success",
        fetched_count=2,
        parsed_count=2,
        new_count=2,
        duplicate_count=0,
        error_count=0,
        error_messages=[],
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
    )

    try:
        with patch("routers.trigger.run_pipeline", return_value=mock_result):
            # 1. First trigger allowed (t=100.0)
            response = client.post("/trigger/sandbox?scenario=happy_path")
            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # 2. Second trigger for same adapter within 60s rejected (t=130.0)
            mock_clock.current_time = 130.0
            response = client.post("/trigger/sandbox?scenario=happy_path")
            assert response.status_code == 429
            assert response.json()["retry_after_seconds"] == 30

            # 3. Different adapter trigger allowed immediately (independent cooldown)
            response = client.post("/trigger/remotive")
            assert response.status_code == 200

            # 4. Third trigger for sandbox allowed after 60s cooldown (t=161.0)
            mock_clock.current_time = 161.0
            response = client.post("/trigger/sandbox?scenario=happy_path")
            assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_trigger_invalid_adapter_scenario():
    """POST /trigger/invalid returns 404; invalid sandbox scenario returns 400."""
    # Invalid adapter
    response = client.post("/trigger/unknown_adapter")
    assert response.status_code == 404

    # Invalid sandbox scenario
    response = client.post("/trigger/sandbox?scenario=invalid_scenario")
    assert response.status_code == 400


@pytest.mark.parametrize("scenario", [
    "happy_path", "rate_limit", "server_error", "timeout",
    "empty", "malformed", "schema_changed", "duplicates"
])
def test_sandbox_jobs_endpoint_scenarios(scenario):
    """Verifies that the /sandbox/jobs endpoint serves all 8 scenarios cleanly."""
    if scenario == "timeout":
        # Skip delay wait in endpoint unit tests by stubbing sleep
        with patch("asyncio.sleep", return_value=None):
            response = client.get(f"/sandbox/jobs?scenario={scenario}")
            assert response.status_code == 200
    else:
        response = client.get(f"/sandbox/jobs?scenario={scenario}")
        # Validate return codes mapping to sandbox behavior
        if scenario == "rate_limit":
            assert response.status_code == 429
        elif scenario == "server_error":
            assert response.status_code == 500
        else:
            assert response.status_code == 200
