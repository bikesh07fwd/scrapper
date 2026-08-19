"""
schemas.py — Pydantic response models / schemas for the API layer.
"""

from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class AdapterHealthResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    state: str = Field(..., serialization_alias="state")
    consecutive_failures: int
    last_success: Optional[datetime] = Field(None, serialization_alias="last_success")
    last_failure: Optional[datetime] = Field(None, serialization_alias="last_failure")


class HealthResponse(BaseModel):
    status: str
    database: str
    adapters: Dict[str, AdapterHealthResponse]


class JobResponse(BaseModel):
    id: int
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    description: Optional[str] = None


class JobListResponse(BaseModel):
    items: List[JobResponse]
    total: int
    limit: int
    offset: int


class IngestionRunResponse(BaseModel):
    run_id: str
    adapter: str
    status: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    fetched_count: int
    parsed_count: int
    new_count: int
    duplicate_count: int
    error_count: int
    error_messages: List[str] = Field(default_factory=list)


class IngestionRunListResponse(BaseModel):
    items: List[IngestionRunResponse]
    total: int
    limit: int
    offset: int


class TriggerResponse(BaseModel):
    run_id: str
    adapter: str
    status: str
    fetched_count: Optional[int] = None
    new_count: Optional[int] = None
    duplicate_count: Optional[int] = None
    error_count: Optional[int] = None
    reason: Optional[str] = None
