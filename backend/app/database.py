from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from backend.app.config import get_settings


settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def ensure_job_schema() -> None:
    statements = [
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_key VARCHAR(512)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_url TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS next_action VARCHAR(64)",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMP",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS follow_up_due_at TIMESTAMP",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS last_follow_up_at TIMESTAMP",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tailoring_required BOOLEAN DEFAULT FALSE NOT NULL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tailored_resume_exists BOOLEAN DEFAULT FALSE NOT NULL",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS decision_reason TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL",
        "UPDATE jobs SET status = 'queued' WHERE status = 'discovered'",
        "UPDATE jobs SET tailoring_required = FALSE WHERE tailoring_required IS NULL",
        "UPDATE jobs SET tailored_resume_exists = FALSE WHERE tailored_resume_exists IS NULL",
    ]

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()