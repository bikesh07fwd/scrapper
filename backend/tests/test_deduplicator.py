"""
tests/test_deduplicator.py — Unit tests for pipeline/deduplicator.py.
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from pipeline.deduplicator import deduplicate_records


class TestDeduplicator:

    async def test_empty_batch(self):
        """Empty incoming batch must return empty list, zero duplicates, and skip DB query."""
        mock_session = AsyncMock()
        new_recs, dup_count = await deduplicate_records(mock_session, [])
        assert new_recs == []
        assert dup_count == 0
        mock_session.execute.assert_not_called()

    async def test_no_existing_records_in_db(self):
        """If database returns no matching records, all unique batch items are new."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        batch = [
            {"external_id": "id-1", "title": "Job 1"},
            {"external_id": "id-2", "title": "Job 2"},
        ]

        new_recs, dup_count = await deduplicate_records(mock_session, batch)
        assert len(new_recs) == 2
        assert dup_count == 0
        # Ensure it executed exactly once (no N+1 behavior)
        assert mock_session.execute.call_count == 1

    async def test_all_records_exist_in_db(self):
        """If database has all records, they are filtered out and counted as duplicates."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["id-1", "id-2"]
        mock_session.execute.return_value = mock_result

        batch = [
            {"external_id": "id-1", "title": "Job 1"},
            {"external_id": "id-2", "title": "Job 2"},
        ]

        new_recs, dup_count = await deduplicate_records(mock_session, batch)
        assert len(new_recs) == 0
        assert dup_count == 2
        assert mock_session.execute.call_count == 1

    async def test_mixed_new_and_duplicate(self):
        """Only new records must remain; existing ones count as duplicates."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["id-2"]  # only id-2 exists
        mock_session.execute.return_value = mock_result

        batch = [
            {"external_id": "id-1", "title": "Job 1"},
            {"external_id": "id-2", "title": "Job 2"},
            {"external_id": "id-3", "title": "Job 3"},
        ]

        new_recs, dup_count = await deduplicate_records(mock_session, batch)
        assert len(new_recs) == 2
        assert new_recs[0]["external_id"] == "id-1"
        assert new_recs[1]["external_id"] == "id-3"
        assert dup_count == 1
        assert mock_session.execute.call_count == 1

    async def test_duplicates_within_incoming_batch(self):
        """Duplicates within the incoming batch must be consolidated and counted."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = ["id-2"]  # id-2 exists in DB
        mock_session.execute.return_value = mock_result

        # Batch: A (new), A (new dup), B (exist), B (exist dup), C (new)
        batch = [
            {"external_id": "id-1", "title": "Job 1 (first)"},
            {"external_id": "id-1", "title": "Job 1 (dup)"},
            {"external_id": "id-2", "title": "Job 2 (first)"},
            {"external_id": "id-2", "title": "Job 2 (dup)"},
            {"external_id": "id-3", "title": "Job 3"},
        ]

        new_recs, dup_count = await deduplicate_records(mock_session, batch)
        # Should retain only unique non-DB items: id-1 (first) and id-3
        assert len(new_recs) == 2
        assert new_recs[0]["external_id"] == "id-1"
        assert new_recs[0]["title"] == "Job 1 (first)"
        assert new_recs[1]["external_id"] == "id-3"

        # Total duplicates:
        # - within-batch duplicates: id-1 (second), id-2 (second) -> 2
        # - database duplicates: id-2 (first) -> 1
        # Total = 3
        assert dup_count == 3
        assert mock_session.execute.call_count == 1
        # The query should check only unique external_ids in batch
        called_args = mock_session.execute.call_args[0][0]
        # Verify compiled SQL is querying the correct IN items (id-1, id-2, id-3)
        # Since it's a select construct, let's verify exact list
