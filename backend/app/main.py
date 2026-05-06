from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import Base, engine, ensure_job_schema, get_db
from backend.app.models import Job
from backend.app.schemas import (
    BatchJobUpdateRequest,
    BatchJobUpdateResponse,
    DashboardSummaryResponse,
    HealthResponse,
    IngestSourceResponse,
    IngestStateResponse,
    JobResponse,
    JobUpdateRequest,
    ScoreExplanationResponse,
)


settings = get_settings()
VALID_STATUSES = {"queued", "shortlisted", "applied", "archived", "not_interested", "discovered"}
VALID_NEXT_ACTIONS = {"apply_now", "resume_tailoring", "research", "follow_up", "archive"}
FOLLOW_UP_INTERVAL_DAYS = 7


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_job_schema()
    yield


app = FastAPI(title="TrashPanda API", version="0.1.0", lifespan=lifespan)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "discovered":
        return "queued"
    return value


def build_score_explanation(job: Job) -> ScoreExplanationResponse:
    text_blob = " ".join(part for part in (job.title, job.summary, job.company) if part).lower()
    keywords = [
        "platform",
        "infrastructure",
        "site reliability",
        "sre",
        "devops",
        "kubernetes",
        "terraform",
        "cloud",
        "automation",
        "linux",
        "python",
        "backend",
    ]
    overlap_hits = sum(1 for keyword in keywords if keyword in text_blob)
    skill_match = min(100, 38 + overlap_hits * 11 + int(job.score // 8))
    tech_stack_overlap = min(100, 20 + overlap_hits * 14)
    resume_keyword_alignment = min(100, 32 + overlap_hits * 10)

    title_blob = (job.title or "").lower()
    if any(level in title_blob for level in ("senior", "staff", "principal", "lead")):
        seniority_match = "stretch"
    elif any(level in title_blob for level in ("mid", "ii", "iii")):
        seniority_match = "aligned"
    elif any(level in title_blob for level in ("intern", "new grad", "entry", "junior")):
        seniority_match = "light"
    else:
        seniority_match = "aligned"

    stability_score = 72
    if "unknown company" in (job.company or "").lower():
        stability_score = 34
    elif "ycombinator" in (job.source_url or "").lower():
        stability_score = 78

    return ScoreExplanationResponse(
        skill_match_percent=skill_match,
        seniority_match=seniority_match,
        tech_stack_overlap=tech_stack_overlap,
        resume_keyword_alignment=resume_keyword_alignment,
        company_stability_score=stability_score,
    )


def compute_lifecycle_state(job: Job, current_time: datetime, in_flight_window_days: int = 45) -> str:
    status = normalize_status(job.status) or "queued"
    if status in {"queued", "shortlisted", "archived", "not_interested"}:
        return status

    applied_at = as_utc(job.applied_at)
    if applied_at is None:
        return status

    age = current_time - applied_at
    if age <= timedelta(days=2):
        return "applied"
    if age <= timedelta(days=in_flight_window_days):
        return "in_flight"
    return "ghosted"


def derive_next_action(job: Job, current_time: datetime, lifecycle_state: str | None = None) -> str:
    if job.next_action in VALID_NEXT_ACTIONS:
        return job.next_action

    lifecycle = lifecycle_state or compute_lifecycle_state(job, current_time)
    title_blob = (job.title or "").lower()
    summary_blob = (job.summary or "").lower()
    company_blob = (job.company or "").lower()

    if lifecycle in {"archived", "not_interested", "ghosted"}:
        return "archive"

    if lifecycle in {"applied", "in_flight"}:
        return "follow_up"

    if job.follow_up_due_at and (as_utc(job.follow_up_due_at) or current_time) <= current_time:
        return "follow_up"

    if job.snoozed_until and (as_utc(job.snoozed_until) or current_time) > current_time:
        return "research"

    if job.tailoring_required and not job.tailored_resume_exists:
        return "resume_tailoring"

    if any(term in title_blob for term in ("product specialist", "new grad", "entry-level")):
        return "archive"

    if "unknown company" in company_blob or "unknown" in (job.location or "").lower():
        return "research"

    if job.score >= 70:
        return "apply_now"

    if job.score >= 58 or any(term in summary_blob for term in ("terraform", "python", "platform", "infrastructure")):
        return "resume_tailoring"

    return "research"


def serialize_job(job: Job, current_time: datetime, in_flight_window_days: int = 45) -> JobResponse:
    lifecycle_state = compute_lifecycle_state(job, current_time, in_flight_window_days)
    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        source=job.source,
        source_url=job.source_url,
        score=job.score,
        status=normalize_status(job.status) or "queued",
        lifecycle_state=lifecycle_state,
        next_action=derive_next_action(job, current_time, lifecycle_state),
        snoozed_until=job.snoozed_until,
        applied_at=job.applied_at,
        follow_up_due_at=job.follow_up_due_at,
        last_follow_up_at=job.last_follow_up_at,
        tailoring_required=job.tailoring_required,
        tailored_resume_exists=job.tailored_resume_exists,
        decision_reason=job.decision_reason,
        score_explanation=build_score_explanation(job),
        summary=job.summary,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def apply_job_update(job: Job, payload: JobUpdateRequest, current_time: datetime) -> None:
    status = normalize_status(payload.status)
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Unsupported status")

    if payload.next_action is not None and payload.next_action not in VALID_NEXT_ACTIONS:
        raise HTTPException(status_code=400, detail="Unsupported next action")

    if payload.snooze_days is not None and payload.snooze_days < 1:
        raise HTTPException(status_code=400, detail="Snooze days must be positive")

    if status == "applied" and payload.applied_at is None and job.applied_at is None:
        raise HTTPException(status_code=400, detail="Applied jobs require an applied date")

    decision_reason = payload.decision_reason.strip() if payload.decision_reason is not None else None
    if status == "not_interested" and not (decision_reason or job.decision_reason):
        raise HTTPException(status_code=400, detail="Not interested requires a reason")

    if status is not None:
        job.status = status

    if payload.applied_at is not None:
        job.applied_at = payload.applied_at

    if status == "applied":
        job.applied_at = payload.applied_at or job.applied_at
        if job.applied_at is None:
            raise HTTPException(status_code=400, detail="Applied jobs require an applied date")
        if job.follow_up_due_at is None:
            follow_up_due = (as_utc(job.applied_at) or current_time) + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)
            job.follow_up_due_at = follow_up_due.replace(tzinfo=None)

    if payload.tailoring_required is not None:
        job.tailoring_required = payload.tailoring_required

    if payload.tailored_resume_exists is not None:
        job.tailored_resume_exists = payload.tailored_resume_exists
        if payload.tailored_resume_exists:
            job.tailoring_required = False

    if decision_reason is not None:
        job.decision_reason = decision_reason or None

    if status == "not_interested":
        job.applied_at = None
        job.follow_up_due_at = None
        job.last_follow_up_at = None
        job.next_action = "archive"

    if status == "queued":
        job.applied_at = None
        job.follow_up_due_at = None
        job.last_follow_up_at = None
        job.decision_reason = None
        job.snoozed_until = None

    if status == "archived":
        job.next_action = "archive"

    if payload.snooze_days is not None:
        job.snoozed_until = (current_time + timedelta(days=payload.snooze_days)).replace(tzinfo=None)
        job.next_action = "research"

    if payload.send_follow_up:
        if job.applied_at is None:
            raise HTTPException(status_code=400, detail="Follow-up requires an applied job")
        job.last_follow_up_at = current_time.replace(tzinfo=None)
        job.follow_up_due_at = (current_time + timedelta(days=FOLLOW_UP_INTERVAL_DAYS)).replace(tzinfo=None)
        job.next_action = "research"

    if payload.next_action is not None:
        job.next_action = payload.next_action

    if job.next_action is None:
        job.next_action = derive_next_action(job, current_time)

    job.updated_at = datetime.utcnow()


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
def list_jobs(db: Session = Depends(get_db)) -> list[JobResponse]:
    current_time = now_utc()
    jobs = db.query(Job).order_by(Job.score.desc(), Job.created_at.desc()).all()
    return [serialize_job(job, current_time) for job in jobs]


@app.get("/api/v1/ingest-state", response_model=IngestStateResponse)
def ingest_state() -> IngestStateResponse:
    state = load_ingest_state()
    state_updated_at = state.get("updated_at")
    sources = [
        IngestSourceResponse(name=name, inserted=inserted, last_ingest_at=state_updated_at, errors=[])
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
    current_time = now_utc()
    jobs = db.query(Job).order_by(Job.score.desc(), Job.created_at.desc()).all()
    lifecycle_counts = {
        "queued": 0,
        "shortlisted": 0,
        "applied": 0,
        "in_flight": 0,
        "ghosted": 0,
        "archived": 0,
    }
    next_action_counts = {key: 0 for key in VALID_NEXT_ACTIONS}

    total_jobs = len(jobs)
    applied_jobs = 0
    in_flight_jobs = 0
    ghosted_jobs = 0
    follow_ups_due = 0
    apps_per_day = 0
    apps_per_week = 0
    pipeline_throughput = 0
    hours_to_apply: list[float] = []

    for job in jobs:
        lifecycle_state = compute_lifecycle_state(job, current_time, in_flight_window_days)
        if lifecycle_state in lifecycle_counts:
            lifecycle_counts[lifecycle_state] += 1
        elif lifecycle_state == "not_interested":
            lifecycle_counts["archived"] += 1

        next_action = derive_next_action(job, current_time, lifecycle_state)
        next_action_counts[next_action] = next_action_counts.get(next_action, 0) + 1

        applied_at = as_utc(job.applied_at)
        if applied_at is not None:
            applied_jobs += 1
            if current_time - applied_at <= timedelta(days=1):
                apps_per_day += 1
            if current_time - applied_at <= timedelta(days=7):
                apps_per_week += 1
            created_at = as_utc(job.created_at) or current_time
            hours_to_apply.append(max(0.0, (applied_at - created_at).total_seconds() / 3600))

        if lifecycle_state == "in_flight":
            in_flight_jobs += 1
        if lifecycle_state == "ghosted":
            ghosted_jobs += 1

        follow_up_due_at = as_utc(job.follow_up_due_at)
        if follow_up_due_at is not None and follow_up_due_at <= current_time and lifecycle_state in {"applied", "in_flight", "ghosted"}:
            follow_ups_due += 1

        updated_at = as_utc(job.updated_at)
        if updated_at is not None and updated_at >= current_time - timedelta(days=7) and lifecycle_state in {"applied", "ghosted", "archived", "not_interested"}:
            pipeline_throughput += 1

    return DashboardSummaryResponse(
        total_jobs=total_jobs,
        applied_jobs=applied_jobs,
        ghosted_jobs=ghosted_jobs,
        ghosted_percent=round((ghosted_jobs / applied_jobs) * 100, 1) if applied_jobs else 0.0,
        in_flight_jobs=in_flight_jobs,
        follow_ups_due=follow_ups_due,
        in_flight_window_days=in_flight_window_days,
        feed_count=state.get("feed_count", len(state.get("sources", {}))),
        lifecycle_counts=lifecycle_counts,
        next_action_counts=next_action_counts,
        apps_per_day=apps_per_day,
        apps_per_week=apps_per_week,
        avg_hours_to_apply=round(sum(hours_to_apply) / len(hours_to_apply), 1) if hours_to_apply else 0.0,
        pipeline_throughput=pipeline_throughput,
        updated_at=state.get("updated_at"),
    )


@app.patch("/api/v1/jobs/{job_id}", response_model=JobResponse)
def update_job(job_id: str, payload: JobUpdateRequest, db: Session = Depends(get_db)) -> Job:
    job = db.query(Job).filter(Job.id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    current_time = now_utc()
    apply_job_update(job, payload, current_time)
    db.add(job)
    db.commit()
    db.refresh(job)
    return serialize_job(job, current_time)


@app.post("/api/v1/jobs/batch-update", response_model=BatchJobUpdateResponse)
def batch_update_jobs(payload: BatchJobUpdateRequest, db: Session = Depends(get_db)) -> BatchJobUpdateResponse:
    if not payload.job_ids:
        raise HTTPException(status_code=400, detail="Select at least one job")

    jobs = db.query(Job).filter(Job.id.in_(payload.job_ids)).all()
    if len(jobs) != len(set(payload.job_ids)):
        raise HTTPException(status_code=404, detail="One or more jobs were not found")

    current_time = now_utc()
    for job in jobs:
        apply_job_update(job, payload, current_time)
        db.add(job)

    db.commit()
    return BatchJobUpdateResponse(updated_jobs=len(jobs))