"""
tests/test_runner.py — Unit tests for pipeline/runner.py.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from adapters.base import BaseAdapter
from pipeline.runner import run_pipeline, RunResult
from pipeline.persister import persist_run_results


class MockAdapter(BaseAdapter):
    name = "mock"

    def __init__(
        self,
        fetch_val=b"raw data",
        parse_val=None,
        should_fail_fetch=False,
        should_fail_parse=False,
    ):
        self.fetch_val = fetch_val
        self.parse_val = parse_val or []
        self.should_fail_fetch = should_fail_fetch
        self.should_fail_parse = should_fail_parse

    async def fetch(self) -> bytes:
        if self.should_fail_fetch:
            raise Exception("Fatal Fetch Exception")
        return self.fetch_val

    def parse(self, raw) -> list[dict]:
        if self.should_fail_parse:
            raise Exception("Fatal Parse Exception")
        return self.parse_val


class AsyncContextManagerMock:
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_db_session():
    from unittest.mock import MagicMock
    session = AsyncMock()
    session.begin = MagicMock(return_value=AsyncContextManagerMock())
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


class TestRunner:

    @patch("pipeline.runner.deduplicate_records")
    async def test_successful_pipeline_run(self, mock_dedup, mock_db_session):
        """Happy path: fetch, parse, validate, normalize, deduplicate, and persist successfully."""
        adapter = MockAdapter(
            parse_val=[
                {"source": "mock", "title": "Job 1", "url": "https://url1.com"},
                {"source": "mock", "title": "Job 2", "url": "https://url2.com"},
            ]
        )

        # Mock deduplicator to return all as new
        mock_dedup.return_value = (
            [
                {"external_id": "h1", "title": "Job 1", "url": "https://url1.com", "source": "mock"},
                {"external_id": "h2", "title": "Job 2", "url": "https://url2.com", "source": "mock"},
            ],
            0,
        )

        result = await run_pipeline(adapter, mock_db_session)

        assert isinstance(result, RunResult)
        assert result.status == "success"
        assert result.fetched_count == 2
        assert result.parsed_count == 2
        assert result.new_count == 2
        assert result.duplicate_count == 0
        assert result.error_count == 0
        assert len(result.error_messages) == 0

        # Persist should be called
        assert mock_db_session.add.call_count == 1  # IngestionRun
        assert mock_db_session.add_all.call_count == 1  # 2 Jobs

    @patch("pipeline.runner.deduplicate_records")
    async def test_partial_validation_failure(self, mock_dedup, mock_db_session):
        """If some records fail validation, they are logged and status becomes partial."""
        adapter = MockAdapter(
            parse_val=[
                {"source": "mock", "title": "Valid Job", "url": "https://valid.com"},
                {"source": "mock", "title": "  ", "url": None},  # Invalid: both empty
            ]
        )

        # Mock deduplicator for the 1 valid record
        mock_dedup.return_value = (
            [{"external_id": "h1", "title": "Valid Job", "url": "https://valid.com", "source": "mock"}],
            0,
        )

        result = await run_pipeline(adapter, mock_db_session)

        assert result.status == "partial"
        assert result.fetched_count == 2
        assert result.parsed_count == 2
        assert result.new_count == 1
        assert result.error_count == 1
        assert len(result.error_messages) == 1
        assert "Record 1" in result.error_messages[0]

        # Ensure persistence succeeded for the single valid record
        assert mock_db_session.add.call_count == 1
        assert mock_db_session.add_all.call_count == 1

    async def test_fatal_fetch_failure(self, mock_db_session):
        """If fetch fails fatally, status becomes failed, IngestionRun is persisted, and error is raised."""
        adapter = MockAdapter(should_fail_fetch=True)

        with pytest.raises(Exception, match="Fatal Fetch Exception"):
            await run_pipeline(adapter, mock_db_session)

        # IngestionRun failure status must be recorded in the DB
        assert mock_db_session.add.call_count == 1
        run_record = mock_db_session.add.call_args[0][0]
        assert run_record.status == "failed"
        assert run_record.fetched_count == 0
        assert run_record.parsed_count == 0
        assert run_record.new_count == 0
        assert "Fatal Fetch Exception" in run_record.error_messages

    async def test_fatal_parse_failure(self, mock_db_session):
        """If parse fails fatally, status becomes failed, IngestionRun is persisted, and error is raised."""
        adapter = MockAdapter(should_fail_parse=True)

        with pytest.raises(Exception, match="Fatal Parse Exception"):
            await run_pipeline(adapter, mock_db_session)

        # IngestionRun failure status must be recorded in the DB
        assert mock_db_session.add.call_count == 1
        run_record = mock_db_session.add.call_args[0][0]
        assert run_record.status == "failed"
        assert "Fatal Parse Exception" in run_record.error_messages

    @patch("pipeline.runner.deduplicate_records")
    async def test_persistence_failure_propagates(self, mock_dedup, mock_db_session):
        """If database save fails, the runner must propagate the error."""
        adapter = MockAdapter(
            parse_val=[{"source": "mock", "title": "Job", "url": "https://url.com"}]
        )
        mock_dedup.return_value = (
            [{"external_id": "h1", "title": "Job", "url": "https://url.com", "source": "mock"}],
            0,
        )

        # Force database insert to raise an exception
        mock_db_session.add_all.side_effect = Exception("DB Connection Lost")

        with pytest.raises(Exception, match="DB Connection Lost"):
            await run_pipeline(adapter, mock_db_session)
