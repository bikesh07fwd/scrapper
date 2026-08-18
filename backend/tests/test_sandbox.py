"""
tests/test_sandbox.py — Integration and endpoint tests for the Sandbox.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import respx
import httpx
from fastapi.testclient import TestClient

from main import app, HAPPY_PATH_XML, EMPTY_XML, MALFORMED_XML, DUPLICATES_XML
from adapters.sandbox import SandboxAdapter
from pipeline.runner import run_pipeline, RunResult
from pipeline.circuit_breaker import STATE_CLOSED, STATE_OPEN, STATE_HALF_OPEN
from models import AdapterHealth, IngestionRun


# FastAPI TestClient for endpoint validation
client = TestClient(app)


class AsyncContextManagerMock:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncContextManagerMock())
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


class TestSandboxEndpoint:

    def test_invalid_scenario_returns_400(self):
        """Passing an unrecognized scenario name must return HTTP 400."""
        response = client.get("/sandbox/jobs?scenario=invalid_scenario_name")
        assert response.status_code == 400
        assert "Invalid scenario" in response.json()["detail"]

    def test_happy_path_scenario_returns_xml(self):
        """happy_path scenario must return application/xml content."""
        response = client.get("/sandbox/jobs?scenario=happy_path")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/xml"
        assert "Sandbox Software Engineer" in response.text

    def test_empty_scenario_returns_empty_xml(self):
        """empty scenario returns valid RSS structure with no items."""
        response = client.get("/sandbox/jobs?scenario=empty")
        assert response.status_code == 200
        assert "Sandbox Feed - Empty" in response.text
        assert "<item>" not in response.text

    def test_malformed_scenario_returns_malformed_xml(self):
        """malformed scenario returns records with missing fields."""
        response = client.get("/sandbox/jobs?scenario=malformed")
        assert response.status_code == 200
        assert "Missing title and link fields completely" in response.text

    def test_duplicates_scenario_returns_duplicates(self):
        """duplicates scenario returns identical entries."""
        response = client.get("/sandbox/jobs?scenario=duplicates")
        assert response.status_code == 200
        assert "Unique Sandbox Lead" in response.text

    def test_rate_limit_returns_429(self):
        """rate_limit scenario returns HTTP 429 and Retry-After header."""
        response = client.get("/sandbox/jobs?scenario=rate_limit")
        assert response.status_code == 429
        assert response.headers["retry-after"] == "1"

    def test_server_error_returns_500(self):
        """server_error scenario returns HTTP 500."""
        response = client.get("/sandbox/jobs?scenario=server_error")
        assert response.status_code == 500


class TestSandboxAdapterAndRunnerIntegration:

    @respx.mock
    async def test_sandbox_happy_path_runner_success(self, mock_db_session):
        """A successful happy_path run updates health to CLOSED/success."""
        # Mock health state as CLOSED
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=2)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        # Mock the local HTTP request
        respx.get("http://127.0.0.1:8000/sandbox/jobs?scenario=happy_path").mock(
            return_value=httpx.Response(200, content=HAPPY_PATH_XML)
        )

        adapter = SandboxAdapter(scenario="happy_path")
        result = await run_pipeline(adapter, mock_db_session)

        assert result.status == "success"
        assert result.fetched_count == 2
        assert result.new_count == 2
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0

    @respx.mock
    async def test_sandbox_empty_response_does_not_open_circuit(self, mock_db_session):
        """An empty RSS response (0 jobs) is a successful run and does NOT open the circuit."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        respx.get("http://127.0.0.1:8000/sandbox/jobs?scenario=empty").mock(
            return_value=httpx.Response(200, content=EMPTY_XML)
        )

        adapter = SandboxAdapter(scenario="empty")
        result = await run_pipeline(adapter, mock_db_session)

        assert result.status == "success"
        assert result.fetched_count == 0
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0

    @respx.mock
    async def test_sandbox_malformed_records_do_not_open_circuit(self, mock_db_session):
        """Validation errors yield a PARTIAL run status, but do NOT count as source failures."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        respx.get("http://127.0.0.1:8000/sandbox/jobs?scenario=malformed").mock(
            return_value=httpx.Response(200, content=MALFORMED_XML)
        )

        adapter = SandboxAdapter(scenario="malformed")
        result = await run_pipeline(adapter, mock_db_session)

        # 1 invalid record is parsed out, status is partial
        assert result.status == "partial"
        assert result.error_count == 1
        # Circuit remains CLOSED, failure count remains 0 (since fetch/parse succeeded)
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0

    @respx.mock
    async def test_sandbox_duplicates_do_not_affect_circuit(self, mock_db_session):
        """Duplicate records are deduplicated but do not affect circuit breaker state."""
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=0)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        respx.get("http://127.0.0.1:8000/sandbox/jobs?scenario=duplicates").mock(
            return_value=httpx.Response(200, content=DUPLICATES_XML)
        )

        # Mock deduplicator to return 1 duplicate
        with patch("pipeline.runner.deduplicate_records") as mock_dedup:
            mock_dedup.return_value = (
                [{"external_id": "lead-1", "title": "Unique Sandbox Lead", "source": "sandbox"}],
                1,
            )

            adapter = SandboxAdapter(scenario="duplicates")
            result = await run_pipeline(adapter, mock_db_session)

            assert result.status == "success"
            assert result.duplicate_count == 1
            assert health.circuit_state == STATE_CLOSED
            assert health.consecutive_failures == 0

    @respx.mock
    async def test_sandbox_repeated_failures_open_circuit(self, mock_db_session):
        """5 consecutive server errors must trip the circuit to OPEN."""
        # Initialize at 4 failures
        health = AdapterHealth(adapter="sandbox", circuit_state=STATE_CLOSED, consecutive_failures=4)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        # Force a 500 error response (this exhausts 3 retries, raising RetryExhaustedError)
        respx.get("http://127.0.0.1:8000/sandbox/jobs?scenario=server_error").mock(
            return_value=httpx.Response(500, content="Error")
        )

        # In tests, change sleep backoff to speed up retries
        with patch("pipeline.fetcher._compute_backoff", return_value=0.01):
            adapter = SandboxAdapter(scenario="server_error")
            with pytest.raises(Exception):
                await run_pipeline(adapter, mock_db_session)

            # Circuit must transition to OPEN
            assert health.circuit_state == STATE_OPEN
            assert health.consecutive_failures == 5
            assert health.circuit_opened_at is not None

    @respx.mock
    async def test_open_circuit_returns_skipped(self, mock_db_session):
        """If circuit state is OPEN, runner immediately skips fetch and returns 'skipped' status."""
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_OPEN,
            circuit_opened_at=datetime.now(timezone.utc),
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        # Spy on SandboxAdapter.fetch to ensure it is never called
        adapter = SandboxAdapter(scenario="happy_path")
        with patch.object(adapter, "fetch", wraps=adapter.fetch) as mock_fetch:
            result = await run_pipeline(adapter, mock_db_session)

            # Return skipped status
            assert result.status == "skipped"
            assert result.error_count == 1
            assert "Circuit breaker is OPEN" in result.error_messages[0]

            # Fetch is blocked
            mock_fetch.assert_not_called()
            # Skipped IngestionRun metadata is created
            assert mock_db_session.add.call_count == 1
            run_rec = mock_db_session.add.call_args[0][0]
            assert isinstance(run_rec, IngestionRun)
            assert run_rec.status == "skipped"

    @respx.mock
    async def test_successful_probe_closes_circuit(self, mock_db_session):
        """If circuit is OPEN but timeout expired, a successful probe returns state to CLOSED."""
        # Set opened_at to 400 seconds ago (expired)
        opened_at = datetime.now(timezone.utc) - timedelta(seconds=400)
        health = AdapterHealth(
            adapter="sandbox",
            circuit_state=STATE_OPEN,
            circuit_opened_at=opened_at,
            consecutive_failures=5,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = health
        mock_db_session.execute.return_value = mock_result

        respx.get("http://127.0.0.1:8000/sandbox/jobs?scenario=happy_path").mock(
            return_value=httpx.Response(200, content=HAPPY_PATH_XML)
        )

        adapter = SandboxAdapter(scenario="happy_path")
        result = await run_pipeline(adapter, mock_db_session)

        assert result.status == "success"
        # Circuit closed, failures reset
        assert health.circuit_state == STATE_CLOSED
        assert health.consecutive_failures == 0
