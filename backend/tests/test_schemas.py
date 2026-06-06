from app.schemas.project import (
    ProjectCreate, ProjectResponse, TBDItem,
    TechStackResponse, EstimationResponse,
)
from app.schemas.document import DocumentResponse
from app.schemas.clarification import ClarificationCreate, ClarificationResponse
from app.schemas.proposal import ProposalResponse
from app.schemas.sync import SyncStatus, SyncResponse
from app.schemas.metrics import MetricsResponse


def test_project_create_fields():
    p = ProjectCreate(name="My Project")
    assert p.name == "My Project"


def test_project_response_fields():
    p = ProjectResponse(
        id="abc", name="Test", status="draft",
        current_phase=1, created_at="2026-01-01T00:00:00Z"
    )
    assert p.current_phase == 1


def test_tbd_item_fields():
    t = TBDItem(id="t1", question="What is the SLA?", level=2, resolved=False)
    assert t.level == 2


def test_sync_status_values():
    assert SyncStatus.pending == "pending"
    assert SyncStatus.synced == "synced"
    assert SyncStatus.skipped == "skipped"
    assert SyncStatus.failed == "failed"


def test_clarification_create_optional_answer():
    c = ClarificationCreate(tbd_id="t1", action="TBD")
    assert c.answer is None


def test_tech_stack_response_fields():
    ts = TechStackResponse(
        frontend=["Next.js"], backend=["FastAPI"],
        database=["SQLite"], infra=["Railway"], rationale="Best fit"
    )
    assert "Next.js" in ts.frontend


def test_estimation_response_fields():
    e = EstimationResponse(
        epics=[{"title": "E1", "estimated_points": 8, "confidence": 0.8}],
        total_points=8, total_weeks=2.0
    )
    assert e.total_points == 8
