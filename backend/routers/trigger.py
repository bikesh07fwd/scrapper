"""
routers/trigger.py — Endpoint to manually trigger ingestion pipeline runs.
"""

import time
from typing import Optional, Dict, Callable
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from pipeline.runner import run_pipeline
from adapters.remotive_rss import RemotiveRSSAdapter
from adapters.sandbox import SandboxAdapter
from schemas import TriggerResponse

router = APIRouter()


class CooldownManager:
    """
    Tracks and enforces a 60-second trigger cooldown per adapter.
    Uses an in-memory dictionary. Testable via clock dependency injection.
    """

    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock
        self.last_triggered: Dict[str, float] = {}

    def get_retry_after(self, adapter: str, cooldown: float = 60.0) -> int:
        now = self.clock()
        last = self.last_triggered.get(adapter, 0.0)
        elapsed = now - last
        if elapsed < cooldown:
            return int(cooldown - elapsed)
        return 0

    def record(self, adapter: str) -> None:
        self.last_triggered[adapter] = self.clock()


# Global in-process singleton
cooldown_manager = CooldownManager()


def get_cooldown_manager() -> CooldownManager:
    """Dependency injection helper for the CooldownManager."""
    return cooldown_manager


@router.post("/trigger/{adapter}", response_model=TriggerResponse)
async def trigger_adapter(
    adapter: str,
    scenario: Optional[str] = Query(None, description="The sandbox scenario to run (sandbox only)"),
    db: AsyncSession = Depends(get_db),
    cd_manager: CooldownManager = Depends(get_cooldown_manager),
):
    """
    Manually triggers an ingestion run for the specified adapter.
    Enforces a 60-second per-adapter cooldown.
    """
    # 1. Validate adapter name
    allowed_adapters = {"remotive", "sandbox"}
    if adapter not in allowed_adapters:
        raise HTTPException(
            status_code=404,
            detail=f"Adapter '{adapter}' not found. Supported: {sorted(allowed_adapters)}",
        )

    # 2. Validate sandbox scenario
    if adapter == "sandbox":
        allowed_scenarios = {
            "happy_path",
            "rate_limit",
            "server_error",
            "timeout",
            "empty",
            "malformed",
            "schema_changed",
            "duplicates",
        }
        if not scenario:
            scenario = "happy_path"
        if scenario not in allowed_scenarios:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid sandbox scenario '{scenario}'. Allowed: {sorted(allowed_scenarios)}",
            )

    # 3. Check trigger cooldown
    retry_after = cd_manager.get_retry_after(adapter)
    if retry_after > 0:
        return JSONResponse(
            status_code=429,
            content={
                "detail": f"Adapter '{adapter}' is on cooldown.",
                "retry_after_seconds": retry_after,
            },
        )

    # 4. Initialize adapter instance
    if adapter == "remotive":
        adapter_instance = RemotiveRSSAdapter()
    else:  # sandbox
        adapter_instance = SandboxAdapter(scenario=scenario)

    # 5. Record trigger timestamp (before pipeline start, to prevent rapid repeat triggering)
    cd_manager.record(adapter)

    # 6. Run pipeline
    try:
        result = await run_pipeline(adapter_instance, db)
    except Exception as exc:
        # Wrap database, network, or parse errors in a clean HTTP 500
        # to prevent raw SQL or system credentials leakage.
        return JSONResponse(
            status_code=500,
            content={
                "detail": f"Pipeline execution failed: {str(exc)}",
            },
        )

    # 7. Map pipeline outcome to trigger response
    if result.status == "skipped":
        return TriggerResponse(
            run_id=result.run_id,
            adapter=adapter,
            status="skipped",
            reason="circuit_open",
        )

    return TriggerResponse(
        run_id=result.run_id,
        adapter=adapter,
        status=result.status,
        fetched_count=result.fetched_count,
        new_count=result.new_count,
        duplicate_count=result.duplicate_count,
        error_count=result.error_count,
    )
