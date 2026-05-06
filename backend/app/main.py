from contextlib import asynccontextmanager
import json
from pathlib import Path

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import Base, engine, get_db
from backend.app.models import Job
from backend.app.schemas import HealthResponse, IngestSourceResponse, IngestStateResponse, JobResponse


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="TrashPanda API", version="0.1.0", lifespan=lifespan)


def load_ingest_state() -> dict:
    state_path = Path(settings.data_dir) / "ingest-state.json"
    if not state_path.exists():
        return {
            "updated_at": None,
            "poll_interval_seconds": 1800,
            "total_jobs": 0,
            "unknown_company_jobs": 0,
            "remote_jobs": 0,
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
        unknown_company_jobs=state.get("unknown_company_jobs", 0),
        remote_jobs=state.get("remote_jobs", 0),
        errors=state.get("errors", []),
        sources=sources,
    )