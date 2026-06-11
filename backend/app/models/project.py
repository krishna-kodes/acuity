from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import DocumentStatus, ProjectPhase, ProjectStatus

if TYPE_CHECKING:
    from app.models.clarification import Clarification


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255))
    phase: Mapped[ProjectPhase] = mapped_column(
        SAEnum(ProjectPhase), default=ProjectPhase.redaction, nullable=False
    )
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus), default=ProjectStatus.draft, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    tech_stack: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    team_suggestion: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    effort_estimates: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    modules_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sync_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    documents: Mapped[list["Document"]] = relationship(back_populates="project")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="project")
    proposal_state: Mapped["ProposalState | None"] = relationship(
        back_populates="project", uselist=False
    )
    clarifications: Mapped[list["Clarification"]] = relationship(
        back_populates="project"
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (Index("ix_documents_project_id", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    anonymized_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus), default=DocumentStatus.uploaded, nullable=False
    )

    project: Mapped["Project"] = relationship(back_populates="documents")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="document")


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        Index("ix_proposals_project_id", "project_id"),
        Index("ix_proposals_document_id", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)
    content_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sections_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_version: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project: Mapped["Project"] = relationship(back_populates="proposals")
    document: Mapped["Document"] = relationship(back_populates="proposals")


class ProposalState(Base):
    __tablename__ = "proposal_state"
    __table_args__ = (
        UniqueConstraint("project_id"),
        Index("ix_proposal_state_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    state_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped["Project"] = relationship(back_populates="proposal_state")
