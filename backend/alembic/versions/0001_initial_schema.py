"""Initial schema — creates jobs, ingestion_runs, and adapter_health tables.

Revision ID: 0001
Revises: (none — this is the first migration)
Create Date: 2026-08-18

Design notes:
- All timestamps use TIMESTAMPTZ (timezone-aware) to avoid UTC vs local time bugs.
- external_id on jobs carries a UNIQUE constraint — this is the enforcement point
  for deduplication. The application computes the hash; Postgres enforces uniqueness.
- adapter on adapter_health is UNIQUE — one health row per named adapter.
- Integer columns use server_default='0' so existing rows are valid if columns
  are added later via ALTER TABLE (downgrade safety).
"""

from alembic import op
import sqlalchemy as sa

# Alembic revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # jobs — one row per unique job listing
    # ------------------------------------------------------------------
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Dedup key: sha256(source + "|" + url), computed by the pipeline
        sa.Column("external_id", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("company", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        # JSON array stored as string: '["python", "remote"]'
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        # HTML stripped, max 500 chars
        sa.Column("description_snippet", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        # Set by Postgres on insert, not by application code
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Full unparsed source record — for debugging only
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_id", name="uq_jobs_external_id"),
    )
    op.create_index("ix_jobs_source", "jobs", ["source"])
    op.create_index("ix_jobs_ingested_at", "jobs", ["ingested_at"])

    # ------------------------------------------------------------------
    # ingestion_runs — one row per adapter run, success or failure
    # ------------------------------------------------------------------
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # UUID assigned at run start — stable identifier across log lines
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("adapter", sa.String(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        # success | partial | failed | skipped
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("fetched_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("parsed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("new_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duplicate_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        # JSON array of error strings, capped to avoid bloat
        sa.Column("error_messages", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_ingestion_runs_run_id"),
    )
    op.create_index("ix_ingestion_runs_adapter", "ingestion_runs", ["adapter"])
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"])

    # ------------------------------------------------------------------
    # adapter_health — one row per adapter, upserted after every run
    # ------------------------------------------------------------------
    op.create_table(
        "adapter_health",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # UNIQUE: exactly one health row per adapter name
        sa.Column("adapter", sa.String(), nullable=False),
        # CLOSED | OPEN | HALF_OPEN
        sa.Column(
            "circuit_state", sa.String(), server_default="CLOSED", nullable=False
        ),
        # Resets to 0 on success, increments on failure
        sa.Column(
            "consecutive_failures", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("circuit_opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("adapter", name="uq_adapter_health_adapter"),
    )


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("adapter_health")
    op.drop_table("ingestion_runs")
    op.drop_table("jobs")
