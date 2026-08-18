"""
pipeline/runner.py — Orchestrates the complete ingestion pipeline.

Pipeline flow:
1. Initialize run metadata (UUID, start time).
2. Fetch raw data from the adapter.
3. Parse raw data into raw records.
4. Validate each record. Log and count validation failures.
5. Normalize valid records. Log and count normalization failures.
6. Deduplicate normalized records (against DB and within batch).
7. Bulk persist new jobs and the IngestionRun summary in a transaction.
8. Return RunResult.

If a fatal exception occurs (fetch/parse/db), rollback is performed,
the run is recorded as failed (if DB is available), and the exception is re-raised.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.base import BaseAdapter
from pipeline.validator import validate_records
from pipeline.normalizer import normalize_record
from pipeline.deduplicator import deduplicate_records
from pipeline.persister import persist_run_results

logger = structlog.get_logger(__name__)


class RunResult(BaseModel):
    run_id: str
    adapter: str
    status: str
    fetched_count: int
    parsed_count: int
    new_count: int
    duplicate_count: int
    error_count: int
    error_messages: list[str]
    started_at: datetime
    finished_at: datetime


async def run_pipeline(adapter: BaseAdapter, db_session: AsyncSession) -> RunResult:
    """
    Orchestrates the entire ingestion pipeline run for a given adapter.

    Args:
        adapter: The source adapter instance.
        db_session: Async database session.

    Returns:
        RunResult summarizing the execution counts and status.

    Raises:
        Exception: Any fatal error (FetchError, database failure) is re-raised
                   after logging and attempting to persist a failed run record.
    """
    run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)
    log = logger.bind(run_id=run_id, adapter=adapter.name)

    log.info("pipeline.run.started", started_at=started_at.isoformat())

    fetched_count = 0
    parsed_count = 0
    new_count = 0
    duplicate_count = 0
    error_count = 0
    error_messages: list[str] = []
    new_records: list[dict] = []

    try:
        # 1. Fetch raw content
        try:
            raw = await adapter.fetch()
        except Exception as exc:
            log.error("pipeline.run.fetch_failed", error=str(exc))
            raise exc

        # 2. Parse raw content
        try:
            raw_records = adapter.parse(raw)
            parsed_count = len(raw_records)
            fetched_count = parsed_count
        except Exception as exc:
            log.error("pipeline.run.parse_failed", error=str(exc))
            raise exc

        # 3. Validate raw records
        valid_raw_records, validation_errors = validate_records(raw_records)
        if validation_errors:
            error_count += len(validation_errors)
            error_messages.extend(validation_errors)
            log.warning("pipeline.run.validation_warnings", count=len(validation_errors))

        # 4. Normalize valid records
        normalized_records = []
        for raw_rec in valid_raw_records:
            try:
                normalized = normalize_record(raw_rec)
                normalized_records.append(normalized)
            except Exception as exc:
                error_count += 1
                title_snip = raw_rec.title or raw_rec.url or "Unknown"
                msg = f"Normalization error for {title_snip}: {exc}"
                error_messages.append(msg)
                log.warning("pipeline.run.normalization_warning", error=str(exc))

        # 5. Deduplicate and Persist inside a single transaction
        async with db_session.begin():
            new_records, duplicate_count = await deduplicate_records(db_session, normalized_records)
            new_count = len(new_records)

            # 6. Determine final status
            # SUCCESS: completed, zero validation/normalization errors
            # PARTIAL: completed, but some records failed validation/normalization
            status = "partial" if error_count > 0 else "success"

            finished_at = datetime.now(timezone.utc)

            run_data = {
                "run_id": run_id,
                "adapter": adapter.name,
                "started_at": started_at,
                "finished_at": finished_at,
                "status": status,
                "fetched_count": fetched_count,
                "parsed_count": parsed_count,
                "new_count": new_count,
                "duplicate_count": duplicate_count,
                "error_count": error_count,
                "error_messages": error_messages,
            }

            # 7. Persist results
            await persist_run_results(db_session, run_data, new_records)

        log.info(
            "pipeline.run.completed",
            status=status,
            new=new_count,
            duplicates=duplicate_count,
            errors=error_count,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )

        return RunResult(
            run_id=run_id,
            adapter=adapter.name,
            status=status,
            fetched_count=fetched_count,
            parsed_count=parsed_count,
            new_count=new_count,
            duplicate_count=duplicate_count,
            error_count=error_count,
            error_messages=error_messages,
            started_at=started_at,
            finished_at=finished_at,
        )

    except Exception as fatal_exc:
        # Record run as failed if possible
        finished_at = datetime.now(timezone.utc)
        error_messages.append(f"Fatal pipeline error: {fatal_exc}")
        error_count += 1

        run_data_failed = {
            "run_id": run_id,
            "adapter": adapter.name,
            "started_at": started_at,
            "finished_at": finished_at,
            "status": "failed",
            "fetched_count": fetched_count,
            "parsed_count": parsed_count,
            "new_count": 0,
            "duplicate_count": 0,
            "error_count": error_count,
            "error_messages": error_messages,
        }

        try:
            # We use a separate transaction to save the failed IngestionRun details
            # if the database is available. If the database itself is dead, this will raise.
            async with db_session.begin():
                await persist_run_results(db_session, run_data_failed, [])
            log.info("pipeline.run.logged_failure", status="failed")
        except Exception as db_exc:
            log.error("pipeline.run.failed_to_log_failure_in_db", db_error=str(db_exc))

        # Propagate original exception so caller/runner knows it failed fatally
        raise fatal_exc
