"""
tests/test_circuit_breaker.py — Unit tests for the circuit breaker.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models import AdapterHealth
from pipeline.circuit_breaker import (
    can_execute,
    record_circuit_success,
    record_circuit_failure,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_HALF_OPEN,
    get_or_create_health,
)


class AsyncContextManagerMock:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_session():
    session = AsyncMock(spec=AsyncSession)
    session.begin = MagicMock(return_value=AsyncContextManagerMock())
    return session


class TestCircuitBreakerState:

    async def test_starts_closed(self, mock_session):
        """Initial state for a new adapter must be CLOSED."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        health = await get_or_create_health(mock_session, "sandbox")
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0

    async def test_successful_request_remains_closed(self, mock_session):
        """A successful request on CLOSED keeps the state as CLOSED and resets failures."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=2)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_success(mock_session, "sandbox")
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0

    async def test_one_failure_increments_count(self, mock_session):
        """A single failure increments consecutive failures but remains CLOSED."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_failure(mock_session, "sandbox", "Timeout Error", 5)
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 1
        assert health.last_error == "Timeout Error"
        assert health.last_failure_at is not None

    async def test_four_failures_remain_closed(self, mock_session):
        """Count grows with consecutive failures, but remains CLOSED under the threshold (5)."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=3)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_failure(mock_session, "sandbox", "Error 4", 5)
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 4

    async def test_fifth_consecutive_failure_trips_to_open(self, mock_session):
        """The fifth consecutive failure trips the state to OPEN and records the timestamp."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=4)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_failure(mock_session, "sandbox", "Error 5", 5)
        assert health.circuit_state == STATE_OPEN
        assert health.consecutive_failures == 5
        assert health.circuit_opened_at is not None

    async def test_success_resets_consecutive_failure_count(self, mock_session):
        """A successful request must reset the failure counter to 0."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=4)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_success(mock_session, "sandbox")
        assert health.consecutive_failures == 0
        assert health.circuit_state == STATE_CLOSED

    async def test_open_blocks_requests(self, mock_session):
        """When OPEN and timeout has not elapsed, requests are blocked."""
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_OPEN,
            circuit_opened_at=datetime.now(timezone.utc),
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        proceed, current_state = await can_execute(mock_session, "sandbox", 300)
        assert proceed is False
        assert current_state == STATE_OPEN

    async def test_open_before_timeout_remains_open(self, mock_session):
        """If elapsed time is less than the wait cooldown, state must remain OPEN."""
        # 100 seconds elapsed out of 300 seconds cooldown
        opened_at = datetime.now(timezone.utc) - timedelta(seconds=100)
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_OPEN,
            circuit_opened_at=opened_at,
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        proceed, current_state = await can_execute(mock_session, "sandbox", 300)
        assert proceed is False
        assert current_state == STATE_OPEN

    async def test_after_timeout_transitions_to_half_open(self, mock_session):
        """After recovery timeout, can_execute transitions to HALF_OPEN to allow a single probe."""
        # 400 seconds elapsed out of 300 seconds cooldown
        opened_at = datetime.now(timezone.utc) - timedelta(seconds=400)
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_OPEN,
            circuit_opened_at=opened_at,
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        proceed, current_state = await can_execute(mock_session, "sandbox", 300)
        assert proceed is True
        assert current_state == STATE_HALF_OPEN
        assert health.circuit_state == STATE_HALF_OPEN

    async def test_successful_half_open_probe_closes_circuit(self, mock_session):
        """A successful probe in HALF_OPEN closes the circuit (CLOSED) and resets count."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_HALF_OPEN, consecutive_failures=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_success(mock_session, "sandbox")
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0

    async def test_failed_half_open_probe_returns_to_open(self, mock_session):
        """A failed probe in HALF_OPEN trips the state back to OPEN and resets cooldown."""
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_HALF_OPEN,
            circuit_opened_at=datetime.now(timezone.utc) - timedelta(seconds=400),
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        await record_circuit_failure(mock_session, "sandbox", "Probe failure", 5)
        assert health.circuit_state == STATE_OPEN
        # consecutive failures increments to 6
        assert health.consecutive_failures == 6
        # opened_at reset to current time
        assert (datetime.now(timezone.utc) - health.circuit_opened_at).total_seconds() < 5.0

    async def test_only_one_half_open_probe_is_allowed(self, mock_session):
        """When in HALF_OPEN state, proceed check is True to execute probe."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_HALF_OPEN, consecutive_failures=5)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        proceed, current_state = await can_execute(mock_session, "sandbox", 300)
        assert proceed is True
        assert current_state == STATE_HALF_OPEN

    async def test_process_restart_preserves_open_state(self, mock_session):
        """State is persisted in DB, so reload from DB preserves the OPEN status."""
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_OPEN,
            circuit_opened_at=datetime.now(timezone.utc),
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_session.execute.return_value = mock_result

        # Simulator process loading state from database
        health_loaded = await get_or_create_health(mock_session, "sandbox")
        assert health_loaded.circuit_state == STATE_OPEN
        assert health_loaded.consecutive_failures == 5
