from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    company: str
    location: str
    source: str
    source_url: str | None
    score: float
    status: str
    applied_at: datetime | None
    decision_reason: str | None
    summary: str
    created_at: datetime
    updated_at: datetime


class HealthResponse(BaseModel):
    status: bool
    database: str
    ai_base_url: str
    ai_model: str


class IngestSourceResponse(BaseModel):
    name: str
    inserted: int


class IngestStateResponse(BaseModel):
    updated_at: datetime | None = None
    poll_interval_seconds: int
    total_jobs: int
    feed_count: int
    errors: list[str]
    sources: list[IngestSourceResponse]


class DashboardSummaryResponse(BaseModel):
    total_jobs: int
    applied_jobs: int
    ghosted_jobs: int
    ghosted_percent: float
    in_flight_jobs: int
    in_flight_window_days: int
    feed_count: int
    updated_at: datetime | None = None


class JobUpdateRequest(BaseModel):
    status: str
    applied_at: datetime | None = None
    decision_reason: str | None = None