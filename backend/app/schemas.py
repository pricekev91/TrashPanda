from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    company: str
    location: str
    source: str
    score: float
    status: str
    summary: str
    created_at: datetime


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
    unknown_company_jobs: int
    remote_jobs: int
    errors: list[str]
    sources: list[IngestSourceResponse]