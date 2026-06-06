from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import TBDAction, TBDLevel, TBDStatus

if TYPE_CHECKING:
    from app.models.project import Project


class Clarification(Base):
    __tablename__ = "clarifications"
    __table_args__ = (Index("ix_clarifications_project_id", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[TBDLevel] = mapped_column(SAEnum(TBDLevel), nullable=False)
    status: Mapped[TBDStatus] = mapped_column(
        SAEnum(TBDStatus), default=TBDStatus.open, nullable=False
    )
    action: Mapped[TBDAction | None] = mapped_column(SAEnum(TBDAction))
    answer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped[Project] = relationship("Project", back_populates="clarifications")
