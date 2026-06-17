from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import SyncStatus


class Epic(Base):
    __tablename__ = "epics"
    __table_args__ = (Index("ix_epics_project_id", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_points: Mapped[int | None] = mapped_column(Integer)
    actual_points: Mapped[int | None] = mapped_column(Integer)  # filled by bidirectional pull
    remote_state: Mapped[str | None] = mapped_column(String(20))  # 'open' | 'closed' (tracker milestone state)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    github_milestone_number: Mapped[int | None] = mapped_column(Integer)
    github_milestone_url: Mapped[str | None] = mapped_column(String(500))
    tracker_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tracker_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tracker_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus), default=SyncStatus.pending, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tasks: Mapped[list["Task"]] = relationship(back_populates="epic")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_epic_id", "epic_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    epic_id: Mapped[int] = mapped_column(Integer, ForeignKey("epics.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_points: Mapped[int | None] = mapped_column(Integer)
    actual_points: Mapped[int | None] = mapped_column(Integer)  # filled by bidirectional pull
    remote_state: Mapped[str | None] = mapped_column(String(20))  # 'open' | 'closed' (tracker issue state)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)
    github_issue_number: Mapped[int | None] = mapped_column(Integer)
    github_issue_url: Mapped[str | None] = mapped_column(String(500))
    tracker_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tracker_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tracker_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus), default=SyncStatus.pending, nullable=False
    )
    labels: Mapped[str | None] = mapped_column(Text)
    assignees: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    epic: Mapped["Epic"] = relationship(back_populates="tasks")
