"""
routers/health.py — Health check endpoint.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import AdapterHealth
from schemas import HealthResponse, AdapterHealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health(db: AsyncSession = Depends(get_db)):
    """
    Checks database connectivity and reports the health states of all configured adapters.
    Returns 503 Service Unavailable if the database is disconnected.
    """
    try:
        # Check database connectivity
        await db.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception:
        database_status = "disconnected"

    if database_status == "disconnected":
        # Return structured unhealthy response with 503 status
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "adapters": {},
            },
        )

    # Database is connected, fetch adapter health states
    adapters_data = {
        "remotive": {
            "state": "CLOSED",
            "consecutive_failures": 0,
            "last_success": None,
            "last_failure": None,
        },
        "sandbox": {
            "state": "CLOSED",
            "consecutive_failures": 0,
            "last_success": None,
            "last_failure": None,
        },
    }

    try:
        stmt = select(AdapterHealth)
        result = await db.execute(stmt)
        records = result.scalars().all()
        for r in records:
            if r.adapter in adapters_data:
                adapters_data[r.adapter] = {
                    "state": r.circuit_state,
                    "consecutive_failures": r.consecutive_failures,
                    "last_success": r.last_success_at.isoformat() if r.last_success_at else None,
                    "last_failure": r.last_failure_at.isoformat() if r.last_failure_at else None,
                }
    except Exception:
        # If DB query fails, degrade health state
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "degraded",
                "adapters": {},
            },
        )

    return HealthResponse(
        status="healthy",
        database="connected",
        adapters=adapters_data,
    )
