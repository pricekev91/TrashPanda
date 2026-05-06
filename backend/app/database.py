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
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS applied_at TIMESTAMP",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS decision_reason TEXT",
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL",
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