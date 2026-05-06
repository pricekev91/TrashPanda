from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.database import Base, engine, get_db
from backend.app.models import Job
from backend.app.schemas import HealthResponse, JobResponse


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="TrashPanda API", version="0.1.0", lifespan=lifespan)


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