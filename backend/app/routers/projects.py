import json
import os
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import (
    DocumentStatus,
    ProjectPhase,
    ProjectStatus,
    TBDAction,
    TBDStatus,
)
from app.models.project import Document, Project, Proposal
from app.models.sync import Epic, Task
from app.schemas.clarification import ClarificationCreate, ClarificationResponse
from app.schemas.document import (
    DocumentResponse,
    ProjectDocumentItem,
    RedactionDecisionResponse,
    RedactionDecisionsUpdate,
    RedactionSummaryResponse,
)
from app.schemas.metrics import MetricsResponse
from app.schemas.project import (
    ChatRequest,
    EstimationResponse,
    ProjectCreate,
    ProjectResponse,
    TBDItem,
    TechStackResponse,
    TeamResponse,
    phase_to_int,
)
from app.schemas.proposal import ProposalResponse
from app.schemas.sync import SyncConfigRequest, SyncConfigResponse, SyncProvider, SyncResponse
from app.services.ingestion import ingest_document
from app.services.workflow import get_workflow

router = APIRouter(tags=["projects"])

# Phases that mean phase 2 (chat) is complete
_POST_CHAT_PHASES = {
    ProjectPhase.techstack, ProjectPhase.team, ProjectPhase.estimation,
    ProjectPhase.epics, ProjectPhase.complete,
}
# Phases that mean phase 4 (team) is complete
_POST_TEAM_PHASES = {
    ProjectPhase.estimation, ProjectPhase.epics, ProjectPhase.complete,
}


def _get_project_or_404(project_id: str, db: Session) -> Project:
    try:
        pid = int(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    project = db.query(Project).filter(Project.id == pid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            domain=p.domain,
            status=p.status.value,
            current_phase=phase_to_int(p.phase.value),
            created_at=p.created_at.isoformat(),
        )
        for p in projects
    ]


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    project = Project(
        name=body.name,
        domain=body.domain,
        status=ProjectStatus.draft,
        phase=ProjectPhase.redaction,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectResponse(
        id=str(project.id),
        name=project.name,
        domain=project.domain,
        status=project.status.value,
        current_phase=phase_to_int(project.phase.value),
        created_at=project.created_at.isoformat(),
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


@router.get(
    "/projects/{project_id}/redaction-decisions",
    response_model=list[RedactionDecisionResponse],
)
def get_redaction_decisions(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[RedactionDecisionResponse]:
    """List detected PII spans for PM review on the redaction screen."""
    from app.models.pii import PIIDetection

    _get_project_or_404(project_id, db)
    latest_doc = (
        db.query(Document)
        .filter(Document.project_id == int(project_id))
        .order_by(Document.upload_ts.desc())
        .first()
    )
    if not latest_doc:
        return []

    detections = (
        db.query(PIIDetection).filter(PIIDetection.document_id == latest_doc.id).all()
    )
    from app.services.pii_detection import decrypt_original
    return [
        RedactionDecisionResponse(
            id=det.id,
            text_original=decrypt_original(det.text_original),
            text_replacement=det.text_replacement,
            pii_type=det.pii_type,
            detection_method=det.detection_method,
            confirmed=det.confirmed,
            overridden=det.overridden,
        )
        for det in detections
    ]


@router.patch(
    "/projects/{project_id}/redaction-decisions",
    response_model=RedactionSummaryResponse,
)
def apply_redaction_decisions(
    project_id: str,
    body: RedactionDecisionsUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RedactionSummaryResponse:
    """PM confirms or overrides each PII span; triggers ingestion completion."""
    from app.models.pii import PIIDetection
    from app.services.ingestion import complete_ingestion

    applied = 0
    skipped = 0

    for item in body.decisions:
        det = db.query(PIIDetection).filter(PIIDetection.id == item.detection_id).first()
        if det is None:
            continue
        if item.confirmed:
            det.confirmed = True
            det.overridden = False
            applied += 1
        else:
            det.confirmed = False
            det.overridden = True
            skipped += 1

    db.commit()

    doc = (
        db.query(Document)
        .filter(
            Document.project_id == int(project_id),
            Document.status == DocumentStatus.anonymising,
        )
        .first()
    )
    if doc:
        background_tasks.add_task(complete_ingestion, doc.id, int(project_id), db)
        status = "ingestion_queued"
    else:
        status = "ingestion_skipped"

    return RedactionSummaryResponse(applied=applied, skipped=skipped, status=status)


@router.get("/projects/{project_id}/tbds", response_model=list[TBDItem])
def get_tbds(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[TBDItem]:
    from app.models.clarification import Clarification
    from app.models.enums import TBDLevel

    _get_project_or_404(project_id, db)
    try:
        pid = int(project_id)
    except ValueError:
        return []

    _tbd_level_int = {
        TBDLevel.explicit: 1, TBDLevel.vague: 2,
        TBDLevel.missing_section: 3, TBDLevel.contradiction: 4,
    }

    tbds = (
        db.query(Clarification)
        .filter(Clarification.project_id == pid, Clarification.status == TBDStatus.open)
        .all()
    )
    return [
        TBDItem(
            id=str(t.id),
            question=t.title,
            level=_tbd_level_int.get(t.level, 1),
            resolved=False,
        )
        for t in tbds
    ]


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
    from app.models.clarification import Clarification
    from app.models.enums import TBDLevel

    _action_to_status = {
        "Answer": TBDStatus.answered,
        "TBD": TBDStatus.tbd,
        "Out-of-Scope": TBDStatus.oos,
    }

    # Try to update an existing clarification
    det = None
    try:
        det = db.query(Clarification).filter(Clarification.id == int(body.tbd_id)).first()
    except (ValueError, TypeError):
        pass

    if det:
        try:
            det.action = TBDAction(body.action)
        except ValueError:
            det.action = None
        det.answer = body.answer
        det.status = _action_to_status.get(body.action, TBDStatus.answered)
        db.commit()
    else:
        try:
            pid = int(project_id)
        except ValueError:
            pid = 0
        try:
            action = TBDAction(body.action)
        except ValueError:
            action = None
        det = Clarification(
            project_id=pid,
            title=f"TBD-{body.tbd_id}",
            description=body.answer or "",
            level=TBDLevel.explicit,
            status=_action_to_status.get(body.action, TBDStatus.answered),
            action=action,
            answer=body.answer,
        )
        db.add(det)
        db.commit()
        db.refresh(det)

    return ClarificationResponse(
        id=str(det.id),
        tbd_id=body.tbd_id,
        action=body.action,
        answer=body.answer,
    )


@router.post("/projects/{project_id}/proposal", response_model=ProposalResponse, status_code=201)
def generate_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    from app.services.exporter import generate_proposal_docx

    project = _get_project_or_404(project_id, db)

    doc = db.query(Document).filter(Document.project_id == project.id).first()
    content = f"Requirements proposal for: {project.name}"
    if doc:
        content += f"\n\nSource document: {doc.filename}"

    content_path = generate_proposal_docx(project.id, project.name, content)

    proposal = Proposal(
        project_id=project.id,
        document_id=doc.id if doc else 0,
        content_path=content_path,
    )
    db.add(proposal)
    project.phase = ProjectPhase.techstack
    db.commit()
    db.refresh(proposal)

    return ProposalResponse(
        id=str(proposal.id),
        project_id=project_id,
        content_path=proposal.content_path,
        created_at=proposal.created_at.isoformat(),
    )


@router.get("/projects/{project_id}/proposal", response_model=ProposalResponse)
def get_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    project = _get_project_or_404(project_id, db)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="No proposal found for this project")

    return ProposalResponse(
        id=str(proposal.id),
        project_id=project_id,
        content_path=proposal.content_path,
        created_at=proposal.created_at.isoformat(),
    )


@router.get("/projects/{project_id}/export/proposal")
def export_proposal(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Download the generated proposal as a DOCX file."""
    project = _get_project_or_404(project_id, db)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="No proposal found for this project")

    if not os.path.exists(proposal.content_path):
        raise HTTPException(status_code=404, detail="Proposal file not found on disk")

    return FileResponse(
        proposal.content_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=proposal_{project_id}.docx"},
    )


@router.get(
    "/projects/{project_id}/documents-list",
    response_model=list[ProjectDocumentItem],
)
def list_project_documents(
    project_id: str,
    db: Session = Depends(get_db),
) -> list[ProjectDocumentItem]:
    """Return all uploaded docs + generated proposals for a project."""
    project = _get_project_or_404(project_id, db)
    items: list[ProjectDocumentItem] = []

    for doc in db.query(Document).filter(Document.project_id == project.id).all():
        file_path = f"documents/{project.id}_{doc.filename}"
        size = None
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
        items.append(ProjectDocumentItem(
            id=str(doc.id),
            doc_type="uploaded",
            filename=doc.filename,
            status=doc.status.value,
            size_bytes=size,
            created_at=doc.upload_ts.isoformat(),
            download_url=f"/api/v1/projects/{project_id}/documents/{doc.id}/download",
        ))

    latest_proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )
    for proposal in ([latest_proposal] if latest_proposal else []):
        size = None
        if os.path.exists(proposal.content_path):
            size = os.path.getsize(proposal.content_path)
        items.append(ProjectDocumentItem(
            id=str(proposal.id),
            doc_type="generated",
            filename=os.path.basename(proposal.content_path),
            status="ready",
            size_bytes=size,
            created_at=proposal.created_at.isoformat(),
            download_url=f"/api/v1/projects/{project_id}/export/proposal",
        ))

    return sorted(items, key=lambda x: x.created_at, reverse=True)


@router.get("/projects/{project_id}/documents/{doc_id}/download")
def download_document(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download the original uploaded requirements document."""
    _get_project_or_404(project_id, db)
    try:
        doc = db.query(Document).filter(
            Document.id == int(doc_id),
            Document.project_id == int(project_id),
        ).first()
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = f"documents/{project_id}_{doc.filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(
        file_path,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(doc.filename)}"},
    )


@router.delete("/projects/{project_id}/documents/{doc_id}", status_code=204)
def delete_document(
    project_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete an uploaded document record and its file on disk."""
    _get_project_or_404(project_id, db)
    try:
        doc = db.query(Document).filter(
            Document.id == int(doc_id),
            Document.project_id == int(project_id),
        ).first()
    except ValueError:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_path = f"documents/{project_id}_{doc.filename}"
    try:
        os.remove(file_path)
    except OSError:
        pass
    db.delete(doc)
    db.commit()


@router.delete("/projects/{project_id}/proposals/{proposal_id}", status_code=204)
def delete_proposal(
    project_id: str,
    proposal_id: str,
    db: Session = Depends(get_db),
) -> None:
    """Delete a generated proposal record and its DOCX file on disk."""
    _get_project_or_404(project_id, db)
    try:
        proposal = db.query(Proposal).filter(
            Proposal.id == int(proposal_id),
            Proposal.project_id == int(project_id),
        ).first()
    except ValueError:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        os.remove(proposal.content_path)
    except OSError:
        pass
    db.delete(proposal)
    db.commit()


@router.post("/projects/{project_id}/stack", response_model=TechStackResponse)
async def suggest_stack(
    project_id: str,
    db: Session = Depends(get_db),
) -> TechStackResponse:
    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_CHAT_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 2 (chat & refinement) must be complete before running tech stack suggestion",
        )

    tech_stack: dict = {}
    try:
        from app.services.workflow import run_phase
        state = await run_phase(str(project.id))
        tech_stack = state.get("tech_stack") or {}
    except Exception:
        pass

    project.tech_stack = tech_stack
    db.commit()

    if project.phase == ProjectPhase.chat:
        project.phase = ProjectPhase.techstack
        db.commit()

    return TechStackResponse(
        frontend=tech_stack.get("frontend", ["Next.js"]),
        backend=tech_stack.get("backend", ["FastAPI"]),
        database=tech_stack.get("database", ["SQLite"]),
        infra=tech_stack.get("infra", ["Railway"]),
        rationale=tech_stack.get("rationale", "Stub — LangGraph not yet invoked for this project."),
    )


@router.post("/projects/{project_id}/team", response_model=TeamResponse)
async def suggest_team(
    project_id: str,
    db: Session = Depends(get_db),
) -> TeamResponse:
    project = _get_project_or_404(project_id, db)

    team: dict = {}
    try:
        from app.services.workflow import run_phase
        state = await run_phase(str(project.id))
        team = state.get("team_suggestion") or {}
    except Exception:
        pass

    project.team_suggestion = team
    if project.phase == ProjectPhase.techstack:
        project.phase = ProjectPhase.team
    db.commit()

    members = team.get("members", [])
    return TeamResponse(members=members, total=len(members))


@router.post("/projects/{project_id}/estimate", response_model=EstimationResponse)
async def estimate_effort(
    project_id: str,
    db: Session = Depends(get_db),
) -> EstimationResponse:
    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_TEAM_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 4 (team suggestion) must be complete before running effort estimation",
        )

    effort: dict = {}
    try:
        from app.services.workflow import run_phase
        state = await run_phase(str(project.id))
        effort = state.get("effort_estimates") or {}
    except Exception:
        pass

    project.effort_estimates = effort
    db.commit()

    if project.phase == ProjectPhase.team:
        project.phase = ProjectPhase.estimation
        db.commit()

    return EstimationResponse(
        epics=effort.get("epics", [{"title": "Stub Epic", "estimated_points": 8, "confidence": 0.8}]),
        total_points=effort.get("total_points", 8),
        total_weeks=effort.get("total_weeks", 2.0),
    )


@router.post("/projects/{project_id}/epics")
async def generate_epics(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict:
    project = _get_project_or_404(project_id, db)

    epics_data: list = []
    try:
        from app.services.workflow import run_phase
        state = await run_phase(str(project.id))
        epics_data = state.get("epics") or []
    except Exception:
        pass

    import json as _json_mod
    for epic_dict in epics_data:
        epic = Epic(
            project_id=int(project_id),
            title=epic_dict["title"],
            description=epic_dict.get("description", ""),
            sync_status="pending",
        )
        db.add(epic)
        db.flush()

        for task_dict in epic_dict.get("tasks", []):
            task = Task(
                epic_id=epic.id,
                title=task_dict["title"],
                description=task_dict.get("description", ""),
                estimated_points=task_dict.get("story_points", 3),
                labels=_json_mod.dumps(task_dict.get("labels", [])),
                sync_status="pending",
            )
            db.add(task)

    db.commit()

    if project.phase == ProjectPhase.estimation:
        project.phase = ProjectPhase.epics
        db.commit()

    return {"epics": epics_data, "count": len(epics_data)}


@router.get("/projects/{project_id}/epics")
def get_epics(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict:
    import json as _json_mod
    _get_project_or_404(project_id, db)
    epics = db.query(Epic).filter(Epic.project_id == int(project_id)).all()
    result = []
    for epic in epics:
        tasks_data = []
        for t in epic.tasks:
            try:
                labels = _json_mod.loads(t.labels) if t.labels else []
            except (_json_mod.JSONDecodeError, TypeError):
                labels = []
            try:
                assignees = _json_mod.loads(t.assignees) if t.assignees else []
            except (_json_mod.JSONDecodeError, TypeError):
                assignees = []
            tasks_data.append({
                "id": t.id,
                "title": t.title,
                "description": t.description,
                "story_points": t.estimated_points or 3,
                "labels": labels,
                "assignees": assignees,
                "sync_status": t.sync_status.value if hasattr(t.sync_status, "value") else str(t.sync_status),
                "github_issue_number": t.github_issue_number,
                "github_issue_url": t.github_issue_url,
            })
        result.append({
            "id": epic.id,
            "title": epic.title,
            "description": epic.description,
            "sync_status": epic.sync_status.value if hasattr(epic.sync_status, "value") else str(epic.sync_status),
            "github_milestone_number": epic.github_milestone_number,
            "github_milestone_url": epic.github_milestone_url,
            "tasks": tasks_data,
        })
    return {"epics": result}


@router.post("/projects/{project_id}/sync", response_model=SyncResponse)
async def sync(
    project_id: str,
    db: Session = Depends(get_db),
) -> SyncResponse:
    import inspect
    import json as _json_mod
    from app.config import settings as _settings
    from app.models.enums import SyncStatus as DBSyncStatus
    from app.services.sync_factory import get_sync_fn

    project = _get_project_or_404(project_id, db)
    epics = db.query(Epic).filter(Epic.project_id == int(project_id)).all()

    epics_payload: list[dict] = []
    epic_task_map: list[tuple] = []

    for epic in epics:
        tasks_payload: list[dict] = []
        task_orms: list = []
        for t in epic.tasks:
            try:
                labels = _json_mod.loads(t.labels) if t.labels else ["task"]
            except (_json_mod.JSONDecodeError, TypeError):
                labels = ["task"]
            try:
                assignees = _json_mod.loads(t.assignees) if t.assignees else []
            except (_json_mod.JSONDecodeError, TypeError):
                assignees = []
            task_dict: dict = {
                "title": t.title,
                "body": t.description or "",
                "labels": labels,
                "assignees": assignees,
            }
            tasks_payload.append(task_dict)
            task_orms.append(t)
        epic_dict: dict = {
            "title": epic.title,
            "description": epic.description or "",
            "due_date": "",
            "tasks": tasks_payload,
        }
        epics_payload.append(epic_dict)
        epic_task_map.append((epic, task_orms))

    provider, _config, sync_fn = get_sync_fn(project)

    if inspect.iscoroutinefunction(sync_fn):
        result = await sync_fn(epics_payload)
    else:
        result = sync_fn(epics_payload)

    for i, (epic_orm, task_orms) in enumerate(epic_task_map):
        epic_dict = epics_payload[i]
        epic_orm.sync_status = DBSyncStatus.synced
        if provider == SyncProvider.github:
            epic_orm.github_milestone_number = epic_dict.get("_milestone_number")
            epic_orm.github_milestone_url = epic_dict.get("_milestone_url")
            epic_orm.tracker_type = "github_milestone"
        else:
            epic_orm.tracker_type = "jira_epic"
        epic_orm.tracker_ref = epic_dict.get("_tracker_ref")
        epic_orm.tracker_url = epic_dict.get("_tracker_url")

        for j, task_orm in enumerate(task_orms):
            task_dict = epic_dict["tasks"][j]
            task_orm.sync_status = DBSyncStatus.synced
            if provider == SyncProvider.github:
                task_orm.github_issue_number = task_dict.get("_issue_number")
                task_orm.github_issue_url = task_dict.get("_issue_url")
                task_orm.tracker_type = "github_issue"
            else:
                task_orm.tracker_type = "jira_story"
            task_orm.tracker_ref = task_dict.get("_tracker_ref")
            task_orm.tracker_url = task_dict.get("_tracker_url")

    db.commit()
    return SyncResponse(**result)


@router.get("/projects/{project_id}/sync-config", response_model=SyncConfigResponse)
def get_sync_config(
    project_id: str,
    db: Session = Depends(get_db),
) -> SyncConfigResponse:
    from app.config import settings as _settings

    project = _get_project_or_404(project_id, db)
    resolved_provider = SyncProvider(project.sync_provider or _settings.sync_provider)
    return SyncConfigResponse(
        provider=resolved_provider,
        config=SyncConfigRequest.model_validate(project.sync_config or {}),
    )


@router.patch("/projects/{project_id}/sync-config", response_model=SyncConfigResponse)
def update_sync_config(
    project_id: str,
    body: SyncConfigRequest,
    db: Session = Depends(get_db),
) -> SyncConfigResponse:
    from app.config import settings as _settings

    project = _get_project_or_404(project_id, db)

    if body.provider is not None:
        project.sync_provider = body.provider.value

    project.sync_config = body.model_dump(exclude_none=True)
    db.commit()
    db.refresh(project)

    resolved_provider = SyncProvider(project.sync_provider or _settings.sync_provider)
    return SyncConfigResponse(
        provider=resolved_provider,
        config=SyncConfigRequest.model_validate(project.sync_config or {}),
    )


@router.post(
    "/projects/{project_id}/chat",
    summary="Phase 2 RAG chat turn (SSE)",
)
async def chat(
    project_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    wf = await get_workflow()
    config = {"configurable": {"thread_id": project_id}}

    existing = await wf.aget_state(config)
    history = list(existing.values.get("chat_messages") or [])
    history.append({"role": "user", "content": body.message})

    state_update = {
        "project_id": project_id,
        "chat_messages": history,
        "chat_proceed": body.proceed,
        "phase_status": existing.values.get("phase_status") or {"phase_1": "complete"},
    }

    async def event_generator():
        try:
            async for event in wf.astream_events(
                state_update, config=config, version="v2"
            ):
                etype = event["event"]
                name = event.get("name", "")

                if etype == "on_chat_model_stream" and name == "chat_response":
                    token = event["data"]["chunk"].content
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                elif etype == "on_chain_end" and name == "chat_turn":
                    output = event["data"].get("output", {})
                    if tbds := output.get("tbd_items"):
                        yield f"data: {json.dumps({'type': 'tbds', 'items': tbds})}\n\n"
                    if (gs := output.get("groundedness_score")) is not None:
                        from app.config import settings
                        flagged = gs < settings.groundedness_threshold
                        payload = {"type": "groundedness", "score": gs, "flagged": flagged}
                        yield f"data: {json.dumps(payload)}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/metrics", response_model=MetricsResponse)
def get_metrics(
    project_id: str,
    db: Session = Depends(get_db),
) -> MetricsResponse:
    import statistics
    from app.models.observability import ErrorLog, LatencyLog, Metric
    from app.schemas.metrics import ErrorPhaseItem, LatencyNodeItem, TokenPhaseItem

    _get_project_or_404(project_id, db)
    pid = int(project_id)

    # Token aggregation
    metric_rows = db.query(Metric).filter(Metric.project_id == pid).all()
    total_tokens = sum(r.input_tokens + r.output_tokens for r in metric_rows)
    total_cost = sum(r.cost_usd for r in metric_rows)
    phase_token_map: dict[str, dict] = {}
    for r in metric_rows:
        e = phase_token_map.setdefault(r.phase, {"tokens": 0, "cost": 0.0})
        e["tokens"] += r.input_tokens + r.output_tokens
        e["cost"] += r.cost_usd

    # Latency aggregation (p50/p95 per node)
    latency_rows = db.query(LatencyLog).filter(LatencyLog.project_id == pid).all()
    node_durations: dict[str, list[float]] = {}
    for r in latency_rows:
        node_durations.setdefault(r.node_name, []).append(r.duration_ms)
    latency_by_node = [
        LatencyNodeItem(
            node=node,
            p50=statistics.median(durations),
            p95=sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0],
        )
        for node, durations in node_durations.items()
    ]
    phase_latencies = {
        node: statistics.median(durations) for node, durations in node_durations.items()
    }

    # Error aggregation per phase
    error_rows = db.query(ErrorLog).filter(ErrorLog.project_id == pid).all()
    phase_error_map: dict[str, int] = {}
    for r in error_rows:
        phase_error_map[r.phase or "unknown"] = phase_error_map.get(r.phase or "unknown", 0) + 1

    return MetricsResponse(
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 6),
        phase_latencies=phase_latencies,
        eval_pass_rate=0.0,
        github_sync_success_rate=0.0,
        tokens_by_phase=[
            TokenPhaseItem(phase=p, tokens=v["tokens"], cost=round(v["cost"], 6))
            for p, v in phase_token_map.items()
        ],
        latency_by_node=latency_by_node,
        errors_by_phase=[
            ErrorPhaseItem(phase=p, errors=c) for p, c in phase_error_map.items()
        ],
        error_count=len(error_rows),
    )
