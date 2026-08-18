"""
models.py — SQLAlchemy ORM models for all three database tables.

Schema decisions:
- external_id: sha256(source + "|" + url) — stable, deterministic deduplication key.
  Computed before DB insert; the UNIQUE constraint is the enforcement mechanism.
- tags: stored as a JSON string rather than a separate table. The tag list is
  read-only after ingestion and never queried by individual tag in the API,
  so a join table would add complexity without benefit at this scale.
- raw_json: stores the full unparsed source record for post-mortem debugging.
  Never rendered in the frontend (XSS prevention).
- All timestamps are timezone-aware (TIMESTAMPTZ in Postgres) to avoid
  ambiguity between UTC and local time.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Job(Base):
    """
    One row per unique job listing, deduplicated by external_id.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Deduplication key: sha256(source + "|" + url). Computed in the pipeline.
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Which adapter ingested this record: "remotive", "sandbox", etc.
    source: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # JSON array serialized as a string: '["python", "remote", "full-time"]'
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # HTML-stripped, truncated to 500 characters. Never rendered as raw HTML.
    description_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Source publish timestamp (UTC). Falls back to ingestion time if missing.
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Set by the DB server on insert — not by application code.
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Full unparsed source record — for debugging only.
    raw_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<Job id={self.id} source={self.source!r} title={self.title!r}>"


class IngestionRun(Base):
    """
    One row per adapter run. Records counts and status for every pipeline execution.
    This is the primary observability surface — the dashboard reads from this table.

    Status values:
    - "success"  — all records fetched, parsed, and persisted without errors
    - "partial"  — some records failed validation or parsing; others were persisted
    - "failed"   — fetch or parse failed; no records were persisted
    - "skipped"  — circuit breaker was OPEN; no attempt was made
    """

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # UUID generated at the start of each run — stable identifier across log lines.
    run_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )

    adapter: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # See docstring for valid values.
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Pipeline stage counts — used to diagnose partial failures.
    fetched_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # JSON array of error strings: ["Record 3: missing title", ...]
    # Capped at a reasonable length to avoid storing megabytes of errors.
    error_messages: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<IngestionRun id={self.id} adapter={self.adapter!r} "
            f"status={self.status!r} new={self.new_count}>"
        )


class AdapterHealth(Base):
    """
    One row per adapter, upserted after every run.
    Stores circuit breaker state and the last known success/failure timestamps.

    Circuit states:
    - CLOSED    — normal; requests flow through
    - OPEN      — suspended; fetch is skipped until circuit_open_wait_seconds elapses
    - HALF_OPEN — one probe request is attempted; success → CLOSED, failure → OPEN
    """

    __tablename__ = "adapter_health"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # One row per adapter name — enforced by UNIQUE constraint.
    adapter: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    circuit_state: Mapped[str] = mapped_column(
        String, nullable=False, default="CLOSED"
    )

    # Resets to 0 on any success; increments on every failure.
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # When the circuit last transitioned to OPEN. Used to calculate probe timing.
    circuit_opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Last error message — shown in the /health endpoint and dashboard.
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AdapterHealth adapter={self.adapter!r} "
            f"circuit={self.circuit_state!r} failures={self.consecutive_failures}>"
        )
