"""
verify_phase3.py — Integration verification script for Phase 3.

This script executes:
1. Real fetch and parse from the Remotive RSS feed.
2. Full pipeline run (Validate, Normalize, Deduplicate, Persist).
3. First run summary (should insert jobs).
4. Second run execution (should result in 0 new jobs, showing deduplication).
5. Querying database tables (jobs, ingestion_runs) to verify counts.

Usage:
    # Ensure DATABASE_URL is set in your .env or environment
    python verify_phase3.py
"""

import asyncio
import os
import sys
from datetime import datetime

import structlog
from sqlalchemy import select, func

# Ensure settings loads correctly
from config import settings
from database import AsyncSessionLocal, engine
from models import Job, IngestionRun
from adapters.remotive_rss import RemotiveRSSAdapter
from pipeline.runner import run_pipeline

# Configure standard console logging for this script
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="YYYY-MM-DD HH:mm:ss", utc=True),
        structlog.dev.ConsoleRenderer(colors=True),
    ]
)
logger = structlog.get_logger(__name__)


async def verify() -> None:
    db_url = os.getenv("DATABASE_URL") or settings.database_url
    if not db_url or "placeholder" in db_url or "localhost" in db_url and not os.getenv("RUNNING_IN_TESTS"):
        print("\n" + "=" * 80)
        print("WARNING: No valid DATABASE_URL is set.")
        print("To run this verification against your live Neon PostgreSQL database:")
        print("1. Create your .env file in the backend directory.")
        print("2. Set DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname?sslmode=require")
        print("3. Run the migrations first: .venv\\Scripts\\python.exe -m alembic upgrade head")
        print("4. Run this script again: .venv\\Scripts\\python.exe verify_phase3.py")
        print("=" * 80 + "\n")
        sys.exit(1)

    print("\nStarting Phase 3 Integration Verification...")
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    adapter = RemotiveRSSAdapter()

    # 1. Pre-flight check (Session 1)
    async with AsyncSessionLocal() as session:
        try:
            await session.execute(select(func.count()).select_from(Job))
        except Exception:
            print("\nERROR: Table 'jobs' does not exist in the database.")
            print("Please run database migrations before running this verification:")
            print("  .venv\\Scripts\\python.exe -m alembic upgrade head\n")
            sys.exit(1)

    # 2. RUN 1 (Session 2)
    print("\n" + "-" * 50)
    print("RUN 1: Ingesting jobs from Remotive RSS...")
    print("-" * 50)

    async with AsyncSessionLocal() as session:
        try:
            result_1 = await run_pipeline(adapter, session)
        except Exception as exc:
            print(f"Fatal run failure on RUN 1: {exc}")
            raise exc

    print(f"Source:      {result_1.adapter}")
    print(f"Run ID:      {result_1.run_id}")
    print(f"Status:      {result_1.status}")
    print(f"Fetched:     {result_1.fetched_count}")
    print(f"Parsed:      {result_1.parsed_count}")
    print(f"New:         {result_1.new_count}")
    print(f"Duplicates:  {result_1.duplicate_count}")
    print(f"Errors:      {result_1.error_count}")
    if result_1.error_messages:
        print("Error Messages:")
        for msg in result_1.error_messages[:5]:
            print(f"  - {msg}")

    # 3. RUN 2 (Session 3)
    print("\n" + "-" * 50)
    print("RUN 2: Ingesting again to verify deduplication...")
    print("-" * 50)

    async with AsyncSessionLocal() as session:
        try:
            result_2 = await run_pipeline(adapter, session)
        except Exception as exc:
            print(f"Fatal run failure on RUN 2: {exc}")
            raise exc

    print(f"Source:      {result_2.adapter}")
    print(f"Run ID:      {result_2.run_id}")
    print(f"Status:      {result_2.status}")
    print(f"Fetched:     {result_2.fetched_count}")
    print(f"Parsed:      {result_2.parsed_count}")
    print(f"New:         {result_2.new_count}")
    print(f"Duplicates:  {result_2.duplicate_count}")
    print(f"Errors:      {result_2.error_count}")

    # Assertions to verify deduplication is working
    print("\n" + "=" * 50)
    print("INTEGRATION VERIFICATION RESULT")
    print("=" * 50)
    if result_2.new_count == 0:
        print("DEDUPLICATION VERIFIED: Success! 2nd run ingested 0 new jobs.")
    else:
        print(f"DEDUPLICATION WARNING: Ingested {result_2.new_count} new jobs on second run.")

    # 4. Database Verification (Session 4)
    print("\nQuerying database counts...")
    async with AsyncSessionLocal() as session:
        job_count = (await session.execute(select(func.count(Job.id)))).scalar_one()
        run_count = (await session.execute(select(func.count(IngestionRun.id)))).scalar_one()

    print(f"Total jobs in database:          {job_count}")
    print(f"Total ingestion runs recorded:   {run_count}")
    print("Verification complete!\n")


if __name__ == "__main__":
    asyncio.run(verify())
