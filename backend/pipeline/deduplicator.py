"""
pipeline/deduplicator.py — Filters duplicate records out of an ingestion batch.

Rules:
- Deduplication is based on external_id.
- One database query is executed to find all matching existing records in bulk.
- Handles duplicate records within the same incoming batch.
- Returns new_records and total duplicate_count.
"""

from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Job


async def deduplicate_records(
    db_session: AsyncSession,
    normalized_records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """
    Deduplicates normalized records against the database and within the batch.

    Args:
        db_session: Async database session.
        normalized_records: List of normalized record dicts.

    Returns:
        A tuple: (list of unique new record dicts, total duplicate count).
    """
    if not normalized_records:
        return [], 0

    unique_batch: list[dict[str, Any]] = []
    seen_in_batch: set[str] = set()
    batch_duplicate_count = 0

    # 1. Deduplicate within the incoming batch
    for rec in normalized_records:
        ext_id = rec["external_id"]
        if ext_id in seen_in_batch:
            batch_duplicate_count += 1
        else:
            seen_in_batch.add(ext_id)
            unique_batch.append(rec)

    # 2. Query DB in bulk for existing external IDs
    ext_ids_to_check = list(seen_in_batch)
    stmt = select(Job.external_id).where(Job.external_id.in_(ext_ids_to_check))
    result = await db_session.execute(stmt)
    existing_ids = set(result.scalars().all())

    # 3. Separate new records from database duplicates
    new_records: list[dict[str, Any]] = []
    db_duplicate_count = 0

    for rec in unique_batch:
        if rec["external_id"] in existing_ids:
            db_duplicate_count += 1
        else:
            new_records.append(rec)

    total_duplicates = batch_duplicate_count + db_duplicate_count
    return new_records, total_duplicates
