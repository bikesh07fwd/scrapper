"""
main.py — FastAPI application entry point.

Phase 1 stub: minimal app to verify imports and connectivity.
Routers, lifespan events, and scheduler are added in later phases.
"""

from fastapi import FastAPI

app = FastAPI(
    title="Job Ingestion Pipeline",
    description=(
        "Acdyon Technologies — Part 1: End-to-end job data ingestion "
        "from public sources with resilience, retry, and circuit breaking."
    ),
    version="1.0.0",
)


@app.get("/", tags=["status"])
async def root():
    """Basic liveness check — confirms the application process is running."""
    return {"status": "ok", "message": "Job Ingestion Pipeline is running"}
