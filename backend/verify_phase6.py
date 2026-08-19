"""
verify_phase6.py — Standalone integration verification script for Phase 6.

Queries /runs before and after the scheduler triggers, confirming the new run is
produced by APScheduler and verifying its properties.
"""

import asyncio
import os
import sys
import time
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any

import httpx


def format_json(data: Any) -> str:
    """Helper to format JSON responses nicely."""
    import json
    return json.dumps(data, indent=2)


async def verify():
    print("\nStarting Phase 6 Scheduler E2E Verification...")
    
    # Set environment variables for the test run:
    # 1. Enable scheduler
    # 2. Configure verification interval of 5 seconds
    env = os.environ.copy()
    env["INGESTION_INTERVAL_SECONDS"] = "5"
    
    startup_time = datetime.now(timezone.utc)
    
    # Start the FastAPI application in a subprocess
    print("Starting FastAPI web server subprocess with INGESTION_INTERVAL_SECONDS=5...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
    
    # Allow 4.0 seconds to boot up (first run triggers at t=5.0s)
    await asyncio.sleep(4.0)
    
    historical_run_ids = set()
    
    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0) as client:
            # --- STEP 1: Query /runs before the first scheduled run completes ---
            print("\nStep 1: Querying initial /runs before scheduled run completes...")
            resp = await client.get("/runs")
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("items", []):
                    historical_run_ids.add(item["run_id"])
                print(f"Recorded {len(historical_run_ids)} historical runs.")
            else:
                print(f"Warning: Failed to fetch initial runs list (status: {resp.status_code})")
                
            # --- STEP 2: Wait for scheduler execution (wait 8.0 seconds) ---
            print("\nStep 2: Waiting 8 seconds for the 5-second interval scheduler job to execute...")
            await asyncio.sleep(8.0)
            
            # --- STEP 3: Query /runs again ---
            print("\nStep 3: Querying /runs again to detect the new run...")
            resp = await client.get("/runs")
            assert resp.status_code == 200, f"Failed to get runs list: {resp.status_code}"
            
            runs_data = resp.json()
            new_runs = []
            for item in runs_data.get("items", []):
                if item["run_id"] not in historical_run_ids:
                    new_runs.append(item)
                    
            assert len(new_runs) >= 1, "Verification FAILED: No new scheduled runs were detected in /runs!"
            
            # Identify the latest scheduled run
            scheduled_run = new_runs[0]
            print(f"Success: Detected a new scheduled run: {scheduled_run['run_id']}")
            
            # --- STEP 4: Verify run properties ---
            print("\nStep 4: Verifying scheduled run metadata...")
            print(f"Run Details:\n{format_json(scheduled_run)}")
            
            # Verify adapter
            assert scheduled_run["adapter"] == "remotive", f"Expected adapter to be 'remotive', got {scheduled_run['adapter']}"
            
            # Verify status is a valid status
            assert scheduled_run["status"] in ["success", "partial", "failed", "skipped"], f"Invalid status: {scheduled_run['status']}"
            
            # Verify started_at is after startup time
            # Format in response: "2026-08-18T14:36:12.327023Z"
            started_at_str = scheduled_run["started_at"].replace("Z", "+00:00")
            started_at_dt = datetime.fromisoformat(started_at_str)
            assert started_at_dt > startup_time, f"Expected started_at {started_at_dt} to be after startup time {startup_time}"
            print("started_at timestamp successfully validated (occurs after scheduler startup).")
            
            # Verify counts are reported
            assert "fetched_count" in scheduled_run
            assert "new_count" in scheduled_run
            assert "duplicate_count" in scheduled_run
            print("Job statistics and execution counts are reported correctly.")
            
            # --- STEP 5: Verify scheduler remains alive ---
            print("\nStep 5: Verifying scheduler server process remains alive...")
            health_resp = await client.get("/health")
            assert health_resp.status_code == 200, f"Server unhealthy: {health_resp.status_code}"
            health_data = health_resp.json()
            assert health_data["database"] == "connected", "Database disconnected"
            print("FastAPI server health check passed.")
            
    finally:
        print("\nStopping background FastAPI server process...")
        server_process.terminate()
        server_process.wait()
        
    print("\nPhase 6 Scheduler E2E Integration Verification Complete!\n")


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify())
