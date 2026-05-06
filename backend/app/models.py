from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="discovered")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)