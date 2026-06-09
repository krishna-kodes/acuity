"""Tests for E5-T6: real CRUD, factory seed, phase guards, DOCX export."""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.main import app
from app.models.base import Base
from app.models.enums import ProjectPhase, ProjectStatus
from app.models.project import Project, Proposal


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------

def test_create_project_persists_to_db(client, db_session):
    resp = client.post("/api/v1/projects", json={"name": "Real Project"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Real Project"
    assert data["status"] == "draft"
    assert data["current_phase"] == 1

    project = db_session.query(Project).filter(Project.name == "Real Project").first()
    assert project is not None
    assert project.phase == ProjectPhase.redaction


def test_create_project_returns_integer_id(client):
    resp = client.post("/api/v1/projects", json={"name": "ID Check"})
    assert resp.status_code == 201
    assert resp.json()["id"].isdigit()


# ---------------------------------------------------------------------------
# TBDs
# ---------------------------------------------------------------------------

def test_get_tbds_returns_empty_for_new_project(client, project_id):
    resp = client.get(f"/api/v1/projects/{project_id}/tbds")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_tbds_invalid_project_id_returns_404(client):
    resp = client.get("/api/v1/projects/not-an-id/tbds")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Clarifications
# ---------------------------------------------------------------------------

def test_create_clarification_persists(client, project_id, db_session):
    from app.models.clarification import Clarification

    resp = client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"tbd_id": "new-item", "action": "Answer", "answer": "We use PostgreSQL"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["action"] == "Answer"
    assert data["answer"] == "We use PostgreSQL"

    row = db_session.query(Clarification).filter(Clarification.answer == "We use PostgreSQL").first()
    assert row is not None


def test_create_clarification_updates_existing(client, project_id, db_session):
    from app.models.clarification import Clarification
    from app.models.enums import TBDLevel, TBDStatus

    # Pre-create a clarification
    clar = Clarification(
        project_id=int(project_id),
        title="Database choice",
        description="Which DB?",
        level=TBDLevel.explicit,
        status=TBDStatus.open,
    )
    db_session.add(clar)
    db_session.commit()
    db_session.refresh(clar)

    resp = client.post(
        f"/api/v1/projects/{project_id}/clarifications",
        json={"tbd_id": str(clar.id), "action": "Answer", "answer": "SQLite for MVP"},
    )
    assert resp.status_code == 201
    db_session.refresh(clar)
    assert clar.answer == "SQLite for MVP"


# ---------------------------------------------------------------------------
# Proposal generation + retrieval
# ---------------------------------------------------------------------------

def test_generate_proposal_creates_docx(client, project_id, db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.exporter.os.makedirs", lambda *a, **kw: None)
    monkeypatch.setattr("app.services.exporter.DocxDocument", lambda: _MockDocx())

    resp = client.post(f"/api/v1/projects/{project_id}/proposal")
    assert resp.status_code == 201
    data = resp.json()
    assert "content_path" in data
    assert str(project_id) in data["content_path"]


class _MockDocx:
    def add_heading(self, *a, **kw): pass
    def add_paragraph(self, *a, **kw): pass
    def save(self, path): pass


def test_get_proposal_returns_latest(client, project_id):
    resp = client.get(f"/api/v1/projects/{project_id}/proposal")
    assert resp.status_code == 200
    data = resp.json()
    assert data["project_id"] == project_id


def test_get_proposal_404_for_unknown_project(client):
    resp = client.get("/api/v1/projects/9999/proposal")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase guards
# ---------------------------------------------------------------------------

def test_stack_409_when_phase_not_ready(client, db_session):
    # Create a project at redaction phase (phase 1, not past chat)
    project = Project(name="Early Project", phase=ProjectPhase.redaction, status=ProjectStatus.draft)
    db_session.add(project)
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project.id}/stack")
    assert resp.status_code == 409


def test_estimate_409_when_phase_not_ready(client, db_session):
    # Create a project at chat phase (needs team phase complete for estimate)
    project = Project(name="Chat Phase Project", phase=ProjectPhase.chat, status=ProjectStatus.draft)
    db_session.add(project)
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project.id}/estimate")
    assert resp.status_code == 409


def test_stack_200_when_phase_ready(client, db_session):
    # Project at techstack phase (past chat) — /stack should succeed
    project = Project(name="Stack Phase Project", phase=ProjectPhase.techstack, status=ProjectStatus.active)
    db_session.add(project)
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project.id}/stack")
    assert resp.status_code == 200
    data = resp.json()
    assert "frontend" in data
    assert "rationale" in data


def test_estimate_200_when_phase_ready(client, db_session):
    # Project at estimation phase — /estimate should succeed
    project = Project(name="Estimate Phase Project", phase=ProjectPhase.estimation, status=ProjectStatus.active)
    db_session.add(project)
    db_session.commit()

    resp = client.post(f"/api/v1/projects/{project.id}/estimate")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_points" in data
    assert "total_weeks" in data


# ---------------------------------------------------------------------------
# Factory seed
# ---------------------------------------------------------------------------

def test_seed_employees_returns_count(client, db_session):
    from app.models.employee import Employee

    resp = client.post("/api/v1/factory/seed-employees")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["seeded"] == 20
    assert db_session.query(Employee).count() == 20


def test_seed_projects_returns_count(client):
    resp = client.post("/api/v1/factory/seed-projects")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["seeded"] == 15


def test_seed_technologies_returns_count(client):
    resp = client.post("/api/v1/factory/seed-technologies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["seeded"] == 22


def test_seed_all_total(client, db_session):
    from app.models.employee import Employee
    from app.models.reference import ApprovedTechnology, HistoricalProject

    resp = client.post("/api/v1/factory/seed-all")
    assert resp.status_code == 200
    data = resp.json()
    assert data["seeded"] == 20 + 15 + 22
    assert db_session.query(Employee).count() == 20
    assert db_session.query(HistoricalProject).count() == 15
    assert db_session.query(ApprovedTechnology).count() == 22


def test_seed_technologies_backfills_tags_on_second_run(client, db_session):
    from app.models.reference import ApprovedTechnology

    # First run: inserts records (tags may be empty for legacy data — simulate by clearing)
    client.post("/api/v1/factory/seed-technologies")
    # Wipe tags to simulate pre-existing tag-less records
    db_session.query(ApprovedTechnology).update({"tags": None})
    db_session.commit()

    # Second run: should upsert and restore tags
    resp = client.post("/api/v1/factory/seed-technologies")
    assert resp.status_code == 200

    next_js = db_session.query(ApprovedTechnology).filter_by(name="Next.js").first()
    assert next_js is not None
    assert next_js.tags is not None
    assert "SPA" in next_js.tags

    sqlite = db_session.query(ApprovedTechnology).filter_by(name="SQLite").first()
    assert sqlite is not None
    assert "prototyping" in sqlite.tags

    postgres = db_session.query(ApprovedTechnology).filter_by(name="PostgreSQL").first()
    assert postgres is not None
    assert "high-scale" in postgres.tags


def test_reset_db_clears_data(client, db_session):
    from app.models.employee import Employee
    from app.services.seeder import seed_employees

    seed_employees(db_session)
    assert db_session.query(Employee).count() == 20

    resp = client.delete("/api/v1/factory/reset-db")
    assert resp.status_code == 200
    db_session.expire_all()
    assert db_session.query(Employee).count() == 0
