import json
import os

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
from app.schemas.sync import SyncResponse
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
    docs = db.query(Document).filter(Document.project_id == int(project_id)).all()
    if not docs:
        return []

    doc_ids = [d.id for d in docs]
    detections = (
        db.query(PIIDetection).filter(PIIDetection.document_id.in_(doc_ids)).all()
    )
    return [
        RedactionDecisionResponse(
            id=det.id,
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
def sync_to_github(
    project_id: str,
    db: Session = Depends(get_db),
) -> SyncResponse:
    import json as _json_mod
    from app.services.github_sync import sync_epics_to_github

    _get_project_or_404(project_id, db)
    epics = db.query(Epic).filter(Epic.project_id == int(project_id)).all()

    epics_payload = []
    for epic in epics:
        tasks_payload = []
        for t in epic.tasks:
            try:
                labels = _json_mod.loads(t.labels) if t.labels else ["task"]
            except (_json_mod.JSONDecodeError, TypeError):
                labels = ["task"]
            try:
                assignees = _json_mod.loads(t.assignees) if t.assignees else []
            except (_json_mod.JSONDecodeError, TypeError):
                assignees = []
            tasks_payload.append({
                "title": t.title,
                "body": t.description or "",
                "labels": labels,
                "assignees": assignees,
            })
        epics_payload.append({
            "title": epic.title,
            "description": epic.description or "",
            "due_date": "",
            "tasks": tasks_payload,
        })

    result = sync_epics_to_github(epics=epics_payload)

    # Update sync_status in DB
    from app.models.enums import SyncStatus as DBSyncStatus
    for epic in epics:
        epic.sync_status = DBSyncStatus.synced
        for t in epic.tasks:
            t.sync_status = DBSyncStatus.synced
    db.commit()

    return SyncResponse(**result)


@router.post(
    "/projects/{project_id}/chat",
    summary="Phase 2 RAG chat turn (SSE)",
)
async def chat(
    project_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    wf = get_workflow()
    config = {"configurable": {"thread_id": project_id}}

    existing = wf.get_state(config)
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

                if etype == "on_chat_model_stream" and name != "groundedness_judge":
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
    _get_project_or_404(project_id, db)
    # TODO(Epic 5 #40): aggregate from metrics + latency_logs tables
    return MetricsResponse(
        total_tokens=0,
        total_cost_usd=0.0,
        phase_latencies={},
        eval_pass_rate=0.0,
        github_sync_success_rate=0.0,
    )
