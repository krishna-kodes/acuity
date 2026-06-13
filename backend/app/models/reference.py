from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ApprovedTechnology(Base):
    __tablename__ = "approved_technologies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    tags: Mapped[str | None] = mapped_column(Text)  # comma-separated use-case tags


class HistoricalProject(Base):
    __tablename__ = "historical_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    estimated_points: Mapped[int | None] = mapped_column(Integer)
    actual_points: Mapped[int | None] = mapped_column(Integer)
    duration_weeks: Mapped[float | None] = mapped_column(Float)
    team_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EstimationOutcome(Base):
    """Realized estimate-vs-actual for a completed project epic.

    Written by the feedback loop once a project's epics are closed on the tracker.
    Kept separate from seed `historical_projects` so the learn-loop corpus stays clean.
    Drives the calibration factor applied to future effort estimates.
    """

    __tablename__ = "estimation_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    epic_id: Mapped[int | None] = mapped_column(Integer)
    domain: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(100))  # dominant task label, e.g. "backend"
    estimated_points: Mapped[int | None] = mapped_column(Integer)
    actual_points: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
