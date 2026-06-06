from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PIIDetection(Base):
    __tablename__ = "pii_detections"
    __table_args__ = (Index("ix_pii_detections_document_id", "document_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)
    text_original: Mapped[str] = mapped_column(String(1000), nullable=False)
    text_replacement: Mapped[str] = mapped_column(String(1000), nullable=False)
    pii_type: Mapped[str] = mapped_column(String(100), nullable=False)
    detection_method: Mapped[str] = mapped_column(String(10), nullable=False)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PIIIngestionLog(Base):
    __tablename__ = "pii_ingestion_logs"
    __table_args__ = (
        Index("ix_pii_ingestion_logs_project_id", "project_id"),
        Index("ix_pii_ingestion_logs_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    document_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("documents.id"))
    event: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
