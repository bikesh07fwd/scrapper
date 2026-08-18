"""
tests/test_persister.py — Unit tests for pipeline/persister.py.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from pipeline.persister import persist_run_results
from models import Job, IngestionRun


class AsyncContextManagerMock:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.should_fail or exc_type is not None:
            # Indicate transaction failure/rollback simulation
            return False
        return True


class TestPersister:

    async def test_persist_new_jobs_and_run_record(self):
        """Must insert both the IngestionRun and all new Job records inside a transaction."""
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncContextManagerMock())
        mock_session.add = MagicMock()
        mock_session.add_all = MagicMock()

        run_data = {
            "run_id": "run-uuid-123",
            "adapter": "remotive",
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
            "status": "success",
            "fetched_count": 5,
            "parsed_count": 5,
            "new_count": 2,
            "duplicate_count": 3,
            "error_count": 0,
            "error_messages": [],
        }

        new_jobs = [
            {"external_id": "ext-1", "title": "Job 1", "source": "remotive"},
            {"external_id": "ext-2", "title": "Job 2", "source": "remotive"},
        ]

        await persist_run_results(mock_session, run_data, new_jobs)

        # Verify add was called for IngestionRun
        assert mock_session.add.call_count == 1
        added_run = mock_session.add.call_args[0][0]
        assert isinstance(added_run, IngestionRun)
        assert added_run.run_id == "run-uuid-123"
        assert added_run.status == "success"

        # Verify add_all was called for Jobs
        assert mock_session.add_all.call_count == 1
        added_jobs = mock_session.add_all.call_args[0][0]
        assert len(added_jobs) == 2
        assert isinstance(added_jobs[0], Job)
        assert added_jobs[0].external_id == "ext-1"
        assert added_jobs[1].external_id == "ext-2"

    async def test_persist_empty_run(self):
        """Must insert IngestionRun even if new jobs list is empty, without deleting anything."""
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncContextManagerMock())
        mock_session.add = MagicMock()
        mock_session.add_all = MagicMock()

        run_data = {
            "run_id": "run-uuid-456",
            "adapter": "remotive",
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
            "status": "success",
            "fetched_count": 10,
            "parsed_count": 10,
            "new_count": 0,
            "duplicate_count": 10,
            "error_count": 0,
            "error_messages": [],
        }

        await persist_run_results(mock_session, run_data, [])

        # IngestionRun should be saved
        assert mock_session.add.call_count == 1
        added_run = mock_session.add.call_args[0][0]
        assert added_run.run_id == "run-uuid-456"

        # No jobs added
        mock_session.add_all.assert_not_called()

    async def test_transaction_rollback_propagates_error(self):
        """Exceptions raised during database write must not be swallowed."""
        mock_session = AsyncMock()
        mock_session.begin = MagicMock(return_value=AsyncContextManagerMock())
        mock_session.add = MagicMock()
        mock_session.add_all = MagicMock(side_effect=Exception("DB Integrity Error"))

        run_data = {
            "run_id": "run-uuid-789",
            "adapter": "remotive",
            "started_at": datetime.now(timezone.utc),
            "finished_at": datetime.now(timezone.utc),
            "status": "success",
            "fetched_count": 1,
            "parsed_count": 1,
            "new_count": 1,
            "duplicate_count": 0,
            "error_count": 0,
            "error_messages": [],
        }
        new_jobs = [{"external_id": "ext-1", "title": "Job 1", "source": "remotive"}]

        with pytest.raises(Exception, match="DB Integrity Error"):
            await persist_run_results(mock_session, run_data, new_jobs)
