"""
routers/jobs.py — Jobs listing and detail endpoints.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Job
from schemas import JobResponse, JobListResponse

router = APIRouter()


def to_job_response(job: Job) -> JobResponse:
    """Helper to convert a SQLAlchemy Job ORM model to JobResponse Pydantic schema."""
    tags_list = []
    if job.tags:
        try:
            parsed = json.loads(job.tags)
            if isinstance(parsed, list):
                tags_list = [str(t) for t in parsed]
        except Exception:
            pass
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        category=job.category,
        tags=tags_list,
        url=job.url,
        published_at=job.published_at,
        description=job.description_snippet,
    )


@router.get("/jobs", response_model=JobListResponse)
async def get_jobs(
    limit: int = Query(20, description="Number of items to return"),
    offset: int = Query(0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns a paginated list of ingested jobs ordered by published_at DESC, id DESC.
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
        count_stmt = select(func.count()).select_from(Job)
        count_res = await db.execute(count_stmt)
        total = count_res.scalar() or 0

        # Items query ordered newest first
        stmt = (
            select(Job)
            .order_by(Job.published_at.desc(), Job.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        jobs = result.scalars().all()
    except Exception as exc:
        # Prevent database raw details leakage
        raise HTTPException(
            status_code=500,
            detail="An error occurred while querying job records.",
        )

    items = [to_job_response(j) for j in jobs]
    return JobListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """
    Returns a single job record.
    """
    try:
        stmt = select(Job).where(Job.id == job_id)
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while querying the job record.",
        )

    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    return to_job_response(job)
