"""
verify_phase7.py — Standalone integration verification script for Phase 7.

Launches both the FastAPI backend server and the Vite React frontend development server,
makes HTTP requests to verify they are healthy and serving, and shuts them down cleanly.
"""

import asyncio
import os
import sys
import time
import subprocess
from datetime import datetime, timezone
from typing import Dict, Any

import httpx


async def verify():
    print("\nStarting Phase 7 Frontend Dashboard E2E Verification...")
    
    # 1. Start backend process
    print("Starting backend FastAPI server on port 8000...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--log-level", "warning"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.join(os.getcwd(), "backend"),
    )
    
    # 2. Start frontend process
    # Find npm path
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    print("Starting frontend Vite dev server on port 5173...")
    frontend_process = subprocess.Popen(
        [npm_cmd, "run", "dev", "--", "--port", "5173", "--host", "127.0.0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=os.path.join(os.getcwd(), "frontend"),
    )
    
    # Allow 6.0 seconds for both servers to spin up
    await asyncio.sleep(6.0)
    
    try:
        # Check backend
        async with httpx.AsyncClient(timeout=15.0) as client:
            print("\nStep 1: Testing backend liveness (/health)...")
            resp = await client.get("http://127.0.0.1:8000/health")
            print(f"Backend Status Code: {resp.status_code}")
            assert resp.status_code == 200, f"Backend health request failed: {resp.status_code}"
            health_data = resp.json()
            print(f"Database status: {health_data.get('database')}")
            
            # Check frontend
            print("\nStep 2: Testing frontend dev server liveness (http://127.0.0.1:5173/)...")
            f_resp = await client.get("http://127.0.0.1:5173/")
            print(f"Frontend Status Code: {f_resp.status_code}")
            assert f_resp.status_code == 200, f"Frontend server failed to serve: {f_resp.status_code}"
            
            html_snippet = f_resp.text[:150]
            print(f"Frontend HTML snippet:\n{html_snippet}...")
            assert "div id=\"root\"" in f_resp.text, "React root element not found in HTML!"
            print("React mount point div id='root' exists in page output.")
            
        print("\nPhase 7 E2E Integration Verification Successful!")
        
    finally:
        print("\nStopping background servers...")
        
        print("Terminating backend server process...")
        backend_process.terminate()
        backend_process.wait()
        
        print("Terminating frontend server process...")
        frontend_process.terminate()
        frontend_process.wait()
        
    print("\nPhase 7 E2E Verification Complete!\n")


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify())
