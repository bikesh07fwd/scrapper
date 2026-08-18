"""
verify_phase4.py — End-to-end integration verification for Phase 4.

This script demonstrates:
1. Circuit starts CLOSED.
2. 5 consecutive server error scenarios trip the circuit breaker to OPEN.
3. Immediately attempting another run blocks fetch and returns 'skipped'.
4. Cooldown recovery wait.
5. Happy path probe execution (OPEN -> HALF_OPEN -> CLOSED).
6. State persistence and counts check in PostgreSQL.

Usage:
    python verify_phase4.py
"""

import asyncio
import os
import sys
import time
import threading
from datetime import datetime, timezone

import uvicorn
from sqlalchemy import select, delete

# Ensure settings loading is correctly configured
from config import settings
# Override settings for verification:
settings.circuit_open_wait_seconds = 10  # Cooldown recovery timeout: 10 seconds
settings.circuit_failure_threshold = 5   # Trip threshold: 5 failures
settings.fetch_max_retries = 1           # Fast failure retries (no long waits)

from database import AsyncSessionLocal, engine
from models import Job, IngestionRun, AdapterHealth
from adapters.sandbox import SandboxAdapter
from pipeline.runner import run_pipeline


def run_local_server():
    """Start local FastAPI server on port 8000 for the sandbox endpoint."""
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="warning")


async def verify() -> None:
    db_url = os.getenv("DATABASE_URL") or settings.database_url
    if not db_url or "placeholder" in db_url:
        print("\nERROR: No valid DATABASE_URL configured in .env.")
        sys.exit(1)

    print("\nStarting Phase 4 Circuit Breaker E2E Verification...")
    print(f"Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")

    # 1. Clean Slate: clear previous run records for sandbox adapter
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(AdapterHealth).where(AdapterHealth.adapter == "sandbox"))
            await session.execute(delete(IngestionRun).where(IngestionRun.adapter == "sandbox"))
            await session.execute(delete(Job).where(Job.source == "sandbox"))
    print("Database cleared of previous sandbox runs.")

    # 2. Start local Uvicorn background thread to serve GET /sandbox/jobs
    print("Starting background dev server...")
    server_thread = threading.Thread(target=run_local_server, daemon=True)
    server_thread.start()
    await asyncio.sleep(2)  # Allow server to boot up

    # ─── STEP 1: Initial State check ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 1: Verify Initial State")
    print("=" * 60)
    async with AsyncSessionLocal() as session:
        stmt = select(AdapterHealth).where(AdapterHealth.adapter == "sandbox")
        res = await session.execute(stmt)
        health = res.scalar_one_or_none()
        state = health.circuit_state if health else "CLOSED (No Record)"
        failures = health.consecutive_failures if health else 0
        print(f"Initial DB State:        {state}")
        print(f"Consecutive Failures:     {failures}")

    # ─── STEP 2: 5 Consecutive Failures ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 2: Simulating 5 consecutive adapter failures (server_error)")
    print("=" * 60)

    adapter_fail = SandboxAdapter(scenario="server_error")

    for i in range(1, 6):
        print(f"\nTriggering failure run #{i}...")
        async with AsyncSessionLocal() as session:
            try:
                await run_pipeline(adapter_fail, session)
            except Exception as exc:
                print(f"Ingestion Run #{i} failed fatally as expected: {exc}")

        # Check health state in database
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(AdapterHealth).where(AdapterHealth.adapter == "sandbox"))
            health = res.scalar_one_or_none()
            print(f"DB Circuit State:        {health.circuit_state}")
            print(f"Consecutive Failures:     {health.consecutive_failures}")

    # ─── STEP 3: Immediate Request when OPEN ─────────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 3: Triggering request immediately when circuit is OPEN")
    print("=" * 60)

    # Attempt happy_path run; should get immediately skipped
    adapter_happy = SandboxAdapter(scenario="happy_path")
    async with AsyncSessionLocal() as session:
        result_skipped = await run_pipeline(adapter_happy, session)
        print(f"Run Status:              {result_skipped.status}")
        print(f"Run ID:                  {result_skipped.run_id}")
        print(f"Error Messages:          {result_skipped.error_messages}")

    # ─── STEP 4: Recovery Cooldown Wait ───────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"STEP 4: Sleeping for {settings.circuit_open_wait_seconds + 1}s to exceed cooldown...")
    print("=" * 60)
    await asyncio.sleep(settings.circuit_open_wait_seconds + 1)
    print("Cooldown wait complete.")

    # ─── STEP 5 & 6: Happy Path Recovery Probe ───────────────────────────────
    print("\n" + "=" * 60)
    print("STEP 5 & 6: Executing recovery probe (should move OPEN -> HALF_OPEN -> CLOSED)")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        result_probe = await run_pipeline(adapter_happy, session)
        print(f"Run Status:              {result_probe.status}")
        print(f"Fetched jobs:            {result_probe.fetched_count}")
        print(f"New jobs:                {result_probe.new_count}")

    # ─── STEP 7: Verify final persisted states in PostgreSQL ──────────────────
    print("\n" + "=" * 60)
    print("STEP 7: PostgreSQL Database State Dump")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        # Load final AdapterHealth
        res_h = await session.execute(select(AdapterHealth).where(AdapterHealth.adapter == "sandbox"))
        final_health = res_h.scalar_one_or_none()

        print("--- ADAPTER HEALTH ---")
        print(f"Adapter:                 {final_health.adapter}")
        print(f"State:                   {final_health.circuit_state}")
        print(f"Consecutive Failures:     {final_health.consecutive_failures}")
        print(f"Last Success:            {final_health.last_success_at}")
        print(f"Last Failure:            {final_health.last_failure_at}")

        # Load IngestionRun history
        res_runs = await session.execute(
            select(IngestionRun).where(IngestionRun.adapter == "sandbox").order_selection()
            if hasattr(select(IngestionRun), "order_selection") else
            select(IngestionRun).where(IngestionRun.adapter == "sandbox").order_by(IngestionRun.id.asc())
        )
        runs = res_runs.scalars().all()

        print("\n--- INGESTION RUNS ---")
        print(f"{'Run ID':<40} | {'Status':<10} | {'New':<5} | {'Dups':<5} | {'Errors':<5}")
        print("-" * 75)
        for run in runs:
            # Mask run_id for clean spacing
            rid_short = f"{run.run_id[:8]}...{run.run_id[-8:]}"
            print(f"{rid_short:<40} | {run.status:<10} | {run.new_count:<5} | {run.duplicate_count:<5} | {run.error_count:<5}")

    print("\nPhase 4 integration verification complete!\n")


if __name__ == "__main__":
    asyncio.run(verify())
