from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import Base, engine, ensure_job_schema, get_db
from backend.app.models import Job
from backend.app.schemas import (
    DashboardSummaryResponse,
    HealthResponse,
    IngestSourceResponse,
    IngestStateResponse,
    JobResponse,
    JobUpdateRequest,
)


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_job_schema()
    yield


app = FastAPI(title="TrashPanda API", version="0.1.0", lifespan=lifespan)


def load_ingest_state() -> dict:
    state_path = Path(settings.data_dir) / "ingest-state.json"
    if not state_path.exists():
        return {
            "updated_at": None,
            "poll_interval_seconds": 1800,
            "total_jobs": 0,
            "feed_count": 0,
            "errors": [],
            "sources": {},
        }

    with state_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


@app.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    db.execute(text("SELECT 1"))
    return HealthResponse(
        status=True,
        database="ok",
        ai_base_url=settings.ai_base_url,
        ai_model=settings.ai_model,
    )


@app.get("/api/v1/jobs", response_model=list[JobResponse])
def list_jobs(db: Session = Depends(get_db)) -> list[Job]:
    return db.query(Job).order_by(Job.score.desc(), Job.created_at.desc()).all()


@app.get("/api/v1/ingest-state", response_model=IngestStateResponse)
def ingest_state() -> IngestStateResponse:
    state = load_ingest_state()
    sources = [
        IngestSourceResponse(name=name, inserted=inserted)
        for name, inserted in state.get("sources", {}).items()
    ]
    return IngestStateResponse(
        updated_at=state.get("updated_at"),
        poll_interval_seconds=state.get("poll_interval_seconds", 1800),
        total_jobs=state.get("total_jobs", 0),
        feed_count=state.get("feed_count", len(sources)),
        errors=state.get("errors", []),
        sources=sources,
    )


@app.get("/api/v1/dashboard-summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    in_flight_window_days: int = Query(default=45, ge=15, le=60),
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    state = load_ingest_state()
    cutoff = datetime.now(timezone.utc) - timedelta(days=in_flight_window_days)

    total_jobs = db.query(func.count(Job.id)).scalar() or 0
    applied_jobs = db.query(func.count(Job.id)).filter(Job.applied_at.is_not(None)).scalar() or 0
    in_flight_jobs = (
        db.query(func.count(Job.id))
        .filter(Job.status == "applied")
        .filter(Job.applied_at.is_not(None))
        .filter(Job.applied_at >= cutoff)
        .scalar()
        or 0
    )
    ghosted_jobs = (
        db.query(func.count(Job.id))
        .filter(Job.status == "applied")
        .filter(Job.applied_at.is_not(None))
        .filter(Job.applied_at < cutoff)
        .scalar()
        or 0
    )

    return DashboardSummaryResponse(
        total_jobs=total_jobs,
        applied_jobs=applied_jobs,
        ghosted_jobs=ghosted_jobs,
        ghosted_percent=round((ghosted_jobs / applied_jobs) * 100, 1) if applied_jobs else 0.0,
        in_flight_jobs=in_flight_jobs,
        in_flight_window_days=in_flight_window_days,
        feed_count=state.get("feed_count", len(state.get("sources", {}))),
        updated_at=state.get("updated_at"),
    )


@app.patch("/api/v1/jobs/{job_id}", response_model=JobResponse)
def update_job(job_id: str, payload: JobUpdateRequest, db: Session = Depends(get_db)) -> Job:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if payload.status not in {"discovered", "applied", "not_interested"}:
        raise HTTPException(status_code=400, detail="Unsupported status")

    if payload.status == "applied" and payload.applied_at is None:
        raise HTTPException(status_code=400, detail="Applied jobs require an applied date")

    if payload.status == "not_interested" and not (payload.decision_reason or "").strip():
        raise HTTPException(status_code=400, detail="Not interested requires a reason")

    job.status = payload.status
    job.applied_at = payload.applied_at if payload.status == "applied" else None
    job.decision_reason = (payload.decision_reason or "").strip() or None
    if payload.status == "discovered":
        job.decision_reason = None

    job.updated_at = datetime.utcnow()
    db.add(job)
    db.commit()
    db.refresh(job)
    return job