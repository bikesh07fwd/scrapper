"""
pipeline/persister.py — Persists jobs and ingestion run metadata to PostgreSQL.

Rules:
- Operations are performed in a database transaction.
- Bulk inserts new Job records.
- Records the IngestionRun run details.
- Never deletes existing jobs (e.g. if the new batch is empty).
- Does not swallow database/integrity exceptions.
"""

import json
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from models import Job, IngestionRun


async def persist_run_results(
    db_session: AsyncSession,
    run_data: dict[str, Any],
    new_jobs_data: list[dict[str, Any]],
) -> None:
    """
    Saves new job records and the ingestion run summary to the database in a transaction.

    Args:
        db_session: Async database session.
        run_data: Dictionary containing IngestionRun metrics.
        new_jobs_data: List of normalized new job dicts.

    Raises:
        Exception: any SQLAlchemy / DB exception, forcing a rollback.
    """
    # 1. Create IngestionRun model instance
    error_msgs = run_data.get("error_messages")
    error_msgs_json = json.dumps(error_msgs) if error_msgs else None

    run_record = IngestionRun(
        run_id=run_data["run_id"],
        adapter=run_data["adapter"],
        started_at=run_data["started_at"],
        finished_at=run_data["finished_at"],
        status=run_data["status"],
        fetched_count=run_data["fetched_count"],
        parsed_count=run_data["parsed_count"],
        new_count=run_data["new_count"],
        duplicate_count=run_data["duplicate_count"],
        error_count=run_data["error_count"],
        error_messages=error_msgs_json,
    )
    db_session.add(run_record)

    # 2. Add Job records if any
    if new_jobs_data:
        jobs = [Job(**job_dict) for job_dict in new_jobs_data]
        db_session.add_all(jobs)
