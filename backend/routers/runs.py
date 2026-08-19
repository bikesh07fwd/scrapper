"""
routers/runs.py — Ingestion runs tracking endpoints.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import IngestionRun
from schemas import IngestionRunResponse, IngestionRunListResponse

router = APIRouter()


def to_run_response(run: IngestionRun) -> IngestionRunResponse:
    """Helper to convert a SQLAlchemy IngestionRun ORM model to IngestionRunResponse Pydantic schema."""
    errs = []
    if run.error_messages:
        try:
            parsed = json.loads(run.error_messages)
            if isinstance(parsed, list):
                errs = [str(e) for e in parsed]
        except Exception:
            pass
    return IngestionRunResponse(
        run_id=run.run_id,
        adapter=run.adapter,
        status=run.status or "unknown",
        started_at=run.started_at,
        finished_at=run.finished_at,
        fetched_count=run.fetched_count if run.fetched_count is not None else 0,
        parsed_count=run.parsed_count if run.parsed_count is not None else 0,
        new_count=run.new_count if run.new_count is not None else 0,
        duplicate_count=run.duplicate_count if run.duplicate_count is not None else 0,
        error_count=run.error_count if run.error_count is not None else 0,
        error_messages=errs,
    )


@router.get("/runs", response_model=IngestionRunListResponse)
async def get_runs(
    limit: int = Query(20, description="Number of items to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a paginated list of past ingestion runs ordered by started_at DESC, id DESC.
    """
    # Quick checks for bounds
    if limit < 0 or offset < 0:
        raise HTTPException(
            status_code=400,
            detail="limit and offset parameters must be non-negative.",
        )
    if limit > 100:
        raise HTTPException(
            status_code=400,
            detail="limit parameter cannot exceed 100.",
        )

    try:
        # Total count query
        count_stmt = select(func.count()).select_from(IngestionRun)
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0

        # Items query ordered chronologically newest first
        stmt = (
            select(IngestionRun)
            .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        runs = result.scalars().all()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while querying ingestion runs.",
        )

    items = [to_run_response(r) for r in runs]
    return IngestionRunListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/runs/{run_id}", response_model=IngestionRunResponse)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns a single ingestion run record.
    """
    try:
        stmt = select(IngestionRun).where(IngestionRun.run_id == run_id)
        result = await db.execute(stmt)
        run = result.scalar_one_or_none()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while querying the run record.",
        )

    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' not found.",
        )

    return to_run_response(run)
