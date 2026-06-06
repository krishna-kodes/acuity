from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import DocumentStatus
from app.models.project import Document
from app.schemas.clarification import ClarificationCreate, ClarificationResponse
from app.schemas.document import DocumentResponse
from app.schemas.metrics import MetricsResponse
from app.schemas.project import (
    EstimationResponse,
    ProjectCreate,
    ProjectResponse,
    TBDItem,
    TechStackResponse,
)
from app.schemas.proposal import ProposalResponse
from app.schemas.sync import SyncResponse
from app.services.ingestion import ingest_document

router = APIRouter(tags=["projects"])


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    # TODO(Epic 5 #35): persist to DB
    return ProjectResponse(
        id="stub-id",
        name=body.name,
        status="draft",
        current_phase=1,
        created_at="2026-01-01T00:00:00Z",
    )


@router.post(
    "/projects/{project_id}/documents",
    summary="Upload requirements document",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    import os
    os.makedirs("documents", exist_ok=True)
    file_path = f"documents/{project_id}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        project_id=int(project_id),
        filename=file.filename or "unknown",
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(
        ingest_document, doc.id, int(project_id), file_path, db
    )

    return DocumentResponse(
        id=str(doc.id),
        project_id=project_id,
        filename=doc.filename,
        status=doc.status.value,
        upload_ts=str(doc.upload_ts),
    )


@router.get("/projects/{project_id}/tbds", response_model=list[TBDItem])
def get_tbds(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[TBDItem]:
    # TODO(Epic 5 #37): retrieve TBDs from LangGraph state
    return []


@router.post(
    "/projects/{project_id}/clarifications",
    response_model=ClarificationResponse,
    status_code=201,
)
def create_clarification(
    project_id: str,
    body: ClarificationCreate,
    db: Session = Depends(get_db),
) -> ClarificationResponse:
    # TODO(Epic 5 #40): persist clarification
    return ClarificationResponse(
        id="stub-clarification-id",
        tbd_id=body.tbd_id,
        action=body.action,
        answer=body.answer,
    )


@router.post("/projects/{project_id}/proposal", response_model=ProposalResponse, status_code=201)
def generate_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    # TODO(Epic 5 #37): trigger LangGraph proposal generation node
    return ProposalResponse(
        id="stub-proposal-id",
        project_id=project_id,
        content_path="documents/stub-proposal.docx",
        created_at="2026-01-01T00:00:00Z",
    )


@router.get("/projects/{project_id}/proposal", response_model=ProposalResponse)
def get_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    # TODO(Epic 5 #40): retrieve from proposals table
    return ProposalResponse(
        id="stub-proposal-id",
        project_id=project_id,
        content_path="documents/stub-proposal.docx",
        created_at="2026-01-01T00:00:00Z",
    )


@router.post("/projects/{project_id}/stack", response_model=TechStackResponse)
def suggest_stack(
    project_id: str,
    db: Session = Depends(get_db),
) -> TechStackResponse:
    # TODO(Epic 5 #37): run tech stack suggestion agent node
    return TechStackResponse(
        frontend=["Next.js"],
        backend=["FastAPI"],
        database=["SQLite"],
        infra=["Railway"],
        rationale="Stub rationale — populated by LangGraph in Epic 5.",
    )


@router.post("/projects/{project_id}/estimate", response_model=EstimationResponse)
def estimate_effort(
    project_id: str,
    db: Session = Depends(get_db),
) -> EstimationResponse:
    # TODO(Epic 5 #37): run effort estimation agent node
    return EstimationResponse(
        epics=[{"title": "Stub Epic", "estimated_points": 8, "confidence": 0.8}],
        total_points=8,
        total_weeks=2.0,
    )


@router.post("/projects/{project_id}/sync", response_model=SyncResponse)
def sync_to_github(
    project_id: str,
    db: Session = Depends(get_db),
) -> SyncResponse:
    # TODO(E5-T1): replace stub epics with rows from epics/tasks tables once DB schema lands
    from app.services.github_sync import sync_epics_to_github
    result = sync_epics_to_github(epics=[])
    return SyncResponse(**result)


@router.get("/projects/{project_id}/metrics", response_model=MetricsResponse)
def get_metrics(
    project_id: str,
    db: Session = Depends(get_db),
) -> MetricsResponse:
    # TODO(Epic 5 #40): aggregate from metrics + latency_logs tables
    return MetricsResponse(
        total_tokens=0,
        total_cost_usd=0.0,
        phase_latencies={},
        eval_pass_rate=0.0,
        github_sync_success_rate=0.0,
    )
