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