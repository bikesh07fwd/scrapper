"""
verify_phase5.py — Standalone integration verification script for Phase 5.

Launches the local FastAPI app in a background thread, runs sequential
requests via httpx.AsyncClient, prints all HTTP status codes, and outputs
structured JSON payloads.
"""

import asyncio
import os
import sys
import time
import threading
from typing import Dict, Any

import httpx
import uvicorn
from sqlalchemy import delete

import subprocess
from database import AsyncSessionLocal
from models import Job, IngestionRun, AdapterHealth


def format_json(data: Any) -> str:
    """Helper to format JSON responses nicely."""
    import json
    return json.dumps(data, indent=2)


async def verify():
    print("\nStarting Phase 5 API Layer E2E Verification...")

    # 1. Clean Slate: Clear sandbox records to ensure clean verification counts
    print("Clearing database sandbox history for a clean run...")
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(delete(AdapterHealth).where(AdapterHealth.adapter == "sandbox"))
            await session.execute(delete(IngestionRun).where(IngestionRun.adapter == "sandbox"))
            await session.execute(delete(Job).where(Job.source == "sandbox"))
    print("Database cleared.")

    # 2. Start local FastAPI server in a separate subprocess
    print("Starting background FastAPI web server on port 8000 (subprocess)...")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    
    # Wait for the subprocess server to start listening
    await asyncio.sleep(4.0)

    try:
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=15.0) as client:
            # --- TEST 1: GET /health (Connected) ---
            print("\n" + "=" * 60)
            print("1. GET /health")
            print("=" * 60)
            resp = await client.get("/health")
            print(f"Status Code: {resp.status_code}")
            print(f"Response:\n{format_json(resp.json())}")

            # --- TEST 2: POST /trigger/sandbox?scenario=happy_path (Success) ---
            print("\n" + "=" * 60)
            print("2. POST /trigger/sandbox?scenario=happy_path")
            print("=" * 60)
            resp = await client.post("/trigger/sandbox?scenario=happy_path")
            print(f"Status Code: {resp.status_code}")
            trigger_data = resp.json()
            print(f"Response:\n{format_json(trigger_data)}")
            known_run_id = trigger_data.get("run_id")

            # --- TEST 3: Immediately repeat trigger (Expected: HTTP 429) ---
            print("\n" + "=" * 60)
            print("3. Immediately repeat trigger (Expected: HTTP 429)")
            print("=" * 60)
            resp = await client.post("/trigger/sandbox?scenario=happy_path")
            print(f"Status Code: {resp.status_code}")
            print(f"Response:\n{format_json(resp.json())}")

            # --- TEST 4: GET /jobs?limit=5&offset=0 ---
            print("\n" + "=" * 60)
            print("4. GET /jobs?limit=5&offset=0")
            print("=" * 60)
            resp = await client.get("/jobs?limit=5&offset=0")
            print(f"Status Code: {resp.status_code}")
            jobs_data = resp.json()
            print(f"Response:\n{format_json(jobs_data)}")
            
            known_job_id = None
            if jobs_data.get("items"):
                known_job_id = jobs_data["items"][0]["id"]

            # --- TEST 5: GET /runs?limit=5&offset=0 ---
            print("\n" + "=" * 60)
            print("5. GET /runs?limit=5&offset=0")
            print("=" * 60)
            resp = await client.get("/runs?limit=5&offset=0")
            print(f"Status Code: {resp.status_code}")
            print(f"Response:\n{format_json(resp.json())}")

            # --- TEST 6: GET /jobs/{known_id} ---
            if known_job_id is not None:
                print("\n" + "=" * 60)
                print(f"6. GET /jobs/{known_job_id} (Known ID)")
                print("=" * 60)
                resp = await client.get(f"/jobs/{known_job_id}")
                print(f"Status Code: {resp.status_code}")
                print(f"Response:\n{format_json(resp.json())}")

            # --- TEST 7: GET /runs/{known_run_id} ---
            if known_run_id:
                print("\n" + "=" * 60)
                print(f"7. GET /runs/{known_run_id} (Known Run UUID)")
                print("=" * 60)
                resp = await client.get(f"/runs/{known_run_id}")
                print(f"Status Code: {resp.status_code}")
                print(f"Response:\n{format_json(resp.json())}")

            # --- TEST 8: GET /sandbox/jobs?scenario=happy_path (Phase 4 Endpoint Check) ---
            print("\n" + "=" * 60)
            print("8. GET /sandbox/jobs?scenario=happy_path")
            print("=" * 60)
            resp = await client.get("/sandbox/jobs?scenario=happy_path")
            print(f"Status Code: {resp.status_code}")
            print(f"Content Type: {resp.headers.get('content-type')}")
            print(f"XML snippet:\n{resp.text[:200]}...")

            # --- TEST 9: GET /sandbox/jobs?scenario=server_error (Phase 4 Endpoint Check) ---
            print("\n" + "=" * 60)
            print("9. GET /sandbox/jobs?scenario=server_error")
            print("=" * 60)
            resp = await client.get("/sandbox/jobs?scenario=server_error")
            print(f"Status Code: {resp.status_code}")
            print(f"Response Text: {resp.text}")

    finally:
        print("\nStopping background FastAPI server process...")
        server_process.terminate()
        server_process.wait()

    print("\nPhase 5 API Layer E2E Integration Verification Complete!\n")


if __name__ == "__main__":
    # Prevent runtime EventLoop issues on Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify())
