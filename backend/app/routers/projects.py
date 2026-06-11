import asyncio
import dataclasses
import json
import os
import re
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
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
    ProjectDetailResponse,
    ProjectResponse,
    TBDItem,
    TechStackResponse,
    TeamResponse,
    TeamUpdateRequest,
    phase_to_int,
)
from app.schemas.modules import ModulePatchRequest, ModulesResponse, ModuleOut
from app.schemas.proposal import ProposalResponse, ProposalRetryRequest, ProposalSectionOut, RegenerateSectionRequest
from app.schemas.proposal_sections import ProposalSectionId, SectionResponse, TEMPLATE_VERSION
from app.schemas.sync import SyncConfigRequest, SyncConfigResponse, SyncProvider, SyncRequest, SyncResponse
from app.services.ingestion import ingest_document
from app.services.workflow import get_workflow

router = APIRouter(tags=["projects"])

# Phases that mean phase 2 (chat) is complete
_POST_CHAT_PHASES = {
    ProjectPhase.modules, ProjectPhase.techstack, ProjectPhase.team, ProjectPhase.estimation,
    ProjectPhase.epics, ProjectPhase.complete,
}
# Phases that mean phase 3 (modules) is complete
_POST_MODULES_PHASES = {
    ProjectPhase.techstack, ProjectPhase.team, ProjectPhase.estimation,
    ProjectPhase.epics, ProjectPhase.complete,
}
# Phases that mean phase 3 (tech stack) is complete
_POST_STACK_PHASES = {
    ProjectPhase.techstack, ProjectPhase.team, ProjectPhase.estimation,
    ProjectPhase.epics, ProjectPhase.complete,
}
# Phases that mean phase 4 (team) is complete
_POST_TEAM_PHASES = {
    ProjectPhase.team, ProjectPhase.estimation, ProjectPhase.epics, ProjectPhase.complete,
}
# Phases that mean phase 5 (estimation) is complete
_POST_ESTIMATION_PHASES = {
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


def _group_paragraphs(lines: list[str]) -> list[list[str]]:
    """Group non-empty lines into paragraph groups split by blank lines."""
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.strip():
            current.append(line.strip())
        else:
            if current:
                groups.append(current)
                current = []
    if current:
        groups.append(current)
    return groups if groups else [[""]]


def _parse_proposal_sections(title: str, text: str) -> "ProposalContent":
    """Parse LLM-generated text into ProposalContent sections."""
    from app.services.exporter import ProposalContent, ProposalSection

    # Try to split on numbered sections (1. Title) or ## headings
    lines = text.strip().split("\n")
    sections: list[ProposalSection] = []
    current_heading = ""
    current_body_lines: list[str] = []

    section_pattern = re.compile(r"^(#{1,3}\s+|[0-9]+\.\s+)(.+)")

    for line in lines:
        m = section_pattern.match(line)
        if m:
            if current_heading:
                sections.append(ProposalSection(
                    heading=current_heading,
                    body="\n\n".join(" ".join(g) for g in _group_paragraphs(current_body_lines)),
                ))
            current_heading = m.group(2).strip()
            current_body_lines = []
        else:
            current_body_lines.append(line)

    if current_heading:
        sections.append(ProposalSection(
            heading=current_heading,
            body="\n\n".join(" ".join(g) for g in _group_paragraphs(current_body_lines)),
        ))

    if not sections:
        # Fallback: no sections detected, put everything in one section
        sections = [ProposalSection(heading="Requirements", body=text.strip())]

    return ProposalContent(title=title, sections=sections)


def _proposal_to_response(proposal: "Proposal", project_id: str) -> ProposalResponse:
    sections: list[ProposalSectionOut] = []
    if proposal.content_json:
        try:
            raw = json.loads(proposal.content_json)
            sections = [ProposalSectionOut(**s) for s in raw.get("sections", [])]
        except Exception:
            pass

    structured_sections: list[SectionResponse] | None = None
    if proposal.sections_json:
        try:
            raw = json.loads(proposal.sections_json)
            structured_sections = [SectionResponse(**s) for s in raw]
        except Exception:
            pass

    return ProposalResponse(
        id=str(proposal.id),
        project_id=project_id,
        content_path=proposal.content_path,
        created_at=proposal.created_at.isoformat(),
        sections=sections,
        structured_sections=structured_sections,
        template_version=proposal.template_version,
    )


def _save_proposal_from_sections(
    project: "Project",
    db: Session,
    structured_sections: list,
) -> "Proposal":
    """Persist DOCX + Proposal row from pre-generated sections. Sync — no LLM calls."""
    from app.services.exporter import generate_proposal_docx
    from app.services.branding import get_branding

    sections_json_str = json.dumps([s.model_dump(mode="json") for s in structured_sections])
    generated_text = "\n\n".join(f"## {s.title}\n{s.content}" for s in structured_sections)
    content = _parse_proposal_sections(project.name, generated_text)
    sections_dicts = [s.model_dump(mode="json") for s in structured_sections]
    branding = get_branding(db)
    content_path = generate_proposal_docx(
        project.id, content, structured_sections=sections_dicts, branding=branding
    )
    doc = db.query(Document).filter(Document.project_id == project.id).first()
    content_dict = dataclasses.asdict(content)
    proposal = Proposal(
        project_id=project.id,
        document_id=doc.id if doc else 0,
        content_path=content_path,
        content_json=json.dumps(content_dict),
        sections_json=sections_json_str,
        template_version=TEMPLATE_VERSION,
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    return proposal


async def _run_proposal_generation(
    project: "Project",
    db: Session,
    extra_feedback: str = "",
) -> "Proposal":
    """Generate structured proposal, persist DOCX + Proposal row. Does NOT advance phase."""
    from app.services.proposal_generator import generate_structured_proposal

    structured_sections = await generate_structured_proposal(
        project, db, additional_context=extra_feedback
    )
    return _save_proposal_from_sections(project, db, structured_sections)


def _tech_preview(ts: dict | None) -> list[str]:
    if not ts:
        return []
    items: list[str] = []
    for k in ("frontend", "backend", "database", "infra"):
        items.extend(ts.get(k) or [])
    return items[:3]


def _module_count(modules_json: str | None) -> int:
    if not modules_json:
        return 0
    try:
        parsed = json.loads(modules_json)
        return len(parsed) if isinstance(parsed, list) else 0
    except Exception:
        return 0


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    include_archived: bool = False,
    db: Session = Depends(get_db),
) -> list[ProjectResponse]:
    from app.models.enums import ProjectStatus as _PS
    q = db.query(Project)
    if not include_archived:
        q = q.filter(Project.status != _PS.archived)
    projects = q.order_by(Project.created_at.desc()).all()
    import re as _re

    def _milestones_url(project_id: int) -> str | None:
        epic = db.query(Epic).filter(
            Epic.project_id == project_id,
            Epic.github_milestone_url.isnot(None),
        ).first()
        if epic and epic.github_milestone_url:
            m = _re.match(r"(https://github\.com/[^/]+/[^/]+)/milestones?/\d+", epic.github_milestone_url)
            if m:
                return m.group(1) + "/milestones"
        return None

    def _doc_filename(project) -> str | None:
        docs = sorted(project.documents, key=lambda d: d.upload_ts) if project.documents else []
        return docs[0].filename if docs else None

    return [
        ProjectResponse(
            id=str(p.id),
            name=p.name,
            domain=p.domain,
            status=p.status.value,
            current_phase=phase_to_int(p.phase.value),
            created_at=p.created_at.isoformat(),
            updated_at=p.updated_at.isoformat(),
            module_count=_module_count(p.modules_json),
            tech_preview=_tech_preview(p.tech_stack),
            total_weeks=(p.effort_estimates or {}).get("total_weeks"),
            team_size=len((p.team_suggestion or {}).get("members") or []),
            milestones_url=_milestones_url(p.id),
            document_filename=_doc_filename(p),
        )
        for p in projects
    ]


@router.patch("/projects/{project_id}/archive", status_code=204)
def archive_project(
    project_id: str,
    db: Session = Depends(get_db),
) -> None:
    from app.models.enums import ProjectStatus as _PS
    project = _get_project_or_404(project_id, db)
    project.status = _PS.archived
    db.commit()


@router.patch("/projects/{project_id}/unarchive", status_code=204)
def unarchive_project(
    project_id: str,
    db: Session = Depends(get_db),
) -> None:
    from app.models.enums import ProjectStatus as _PS
    project = _get_project_or_404(project_id, db)
    project.status = _PS.active
    db.commit()


@router.get("/projects/{project_id}", response_model=ProjectDetailResponse)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProjectDetailResponse:
    project = _get_project_or_404(project_id, db)
    summary: str | None = None
    if project.proposals:
        latest = max(project.proposals, key=lambda p: p.created_at)
        if latest.content_json:
            try:
                raw = json.loads(latest.content_json)
                for s in raw.get("sections", []):
                    if s.get("heading", "").lower().startswith("executive summary"):
                        body = s.get("body", "").strip()
                        if body:
                            summary = body[:250] + "…" if len(body) > 250 else body
                        break
            except Exception:
                pass
    return ProjectDetailResponse(
        id=str(project.id),
        name=project.name,
        domain=project.domain,
        status=project.status.value,
        current_phase=phase_to_int(project.phase.value),
        created_at=project.created_at.isoformat(),
        summary=summary,
    )


@router.get("/projects/{project_id}/live-status")
def get_live_status(
    project_id: str,
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone, timedelta
    from app.models.observability import Metric, LatencyLog
    from app.schemas.live_status import LiveStatusResponse, PHASE_AGENT_NAMES

    _get_project_or_404(project_id, db)
    pid = int(project_id)

    rows = db.query(Metric).filter(Metric.project_id == pid).all()
    total_tokens = sum(r.input_tokens + r.output_tokens for r in rows)
    total_cost = sum(r.cost_usd for r in rows)
    llm_call_count = len(rows)

    latest_metric = (
        db.query(Metric)
        .filter(Metric.project_id == pid)
        .order_by(Metric.created_at.desc())
        .first()
    )

    latest_latency = (
        db.query(LatencyLog)
        .filter(LatencyLog.project_id == pid)
        .order_by(LatencyLog.created_at.desc())
        .first()
    )

    agent: str | None = None
    model: str | None = None
    active_phase: str | None = None
    is_recent = False

    if latest_metric:
        active_phase = latest_metric.phase
        agent = PHASE_AGENT_NAMES.get(latest_metric.phase)
        model = latest_metric.model
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
        ts = latest_metric.created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        is_recent = ts >= cutoff

    return LiveStatusResponse(
        agent=agent,
        model=model,
        total_tokens=total_tokens,
        session_cost_usd=round(total_cost, 4),
        last_node=latest_latency.node_name if latest_latency else None,
        last_latency_ms=latest_latency.duration_ms if latest_latency else None,
        llm_call_count=llm_call_count,
        active_phase=active_phase,
        token_budget=100_000,
        is_recent=is_recent,
    )


@router.get("/projects/{project_id}/live-status/stream")
async def live_status_stream(
    project_id: str,
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone, timedelta
    from app.database import SessionLocal
    from app.models.observability import Metric, LatencyLog
    from app.schemas.live_status import LiveStatusResponse, PHASE_AGENT_NAMES

    _get_project_or_404(project_id, db)
    pid = int(project_id)

    def _build_snapshot() -> tuple[LiveStatusResponse, int | None, int | None]:
        session = SessionLocal()
        try:
            rows = session.query(Metric).filter(Metric.project_id == pid).all()
            total_tokens = sum(r.input_tokens + r.output_tokens for r in rows)
            total_cost = sum(r.cost_usd for r in rows)
            llm_call_count = len(rows)

            latest_metric = (
                session.query(Metric)
                .filter(Metric.project_id == pid)
                .order_by(Metric.created_at.desc())
                .first()
            )
            latest_latency = (
                session.query(LatencyLog)
                .filter(LatencyLog.project_id == pid)
                .order_by(LatencyLog.created_at.desc())
                .first()
            )

            agent: str | None = None
            model: str | None = None
            active_phase: str | None = None
            is_recent = False

            if latest_metric:
                active_phase = latest_metric.phase
                agent = PHASE_AGENT_NAMES.get(latest_metric.phase)
                model = latest_metric.model
                cutoff = datetime.now(timezone.utc) - timedelta(seconds=120)
                ts = latest_metric.created_at
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                is_recent = ts >= cutoff

            return (
                LiveStatusResponse(
                    agent=agent,
                    model=model,
                    total_tokens=total_tokens,
                    session_cost_usd=round(total_cost, 4),
                    last_node=latest_latency.node_name if latest_latency else None,
                    last_latency_ms=latest_latency.duration_ms if latest_latency else None,
                    llm_call_count=llm_call_count,
                    active_phase=active_phase,
                    token_budget=100_000,
                    is_recent=is_recent,
                ),
                latest_metric.id if latest_metric else None,
                latest_latency.id if latest_latency else None,
            )
        finally:
            session.close()

    async def generate():
        last_metric_id: int | None = None
        last_latency_id: int | None = None
        try:
            while True:
                snapshot, cur_metric_id, cur_latency_id = await asyncio.get_event_loop().run_in_executor(
                    None, _build_snapshot
                )

                if cur_metric_id != last_metric_id or cur_latency_id != last_latency_id:
                    last_metric_id = cur_metric_id
                    last_latency_id = cur_latency_id
                    yield f"data: {snapshot.model_dump_json()}\n\n"

                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
        updated_at=project.updated_at.isoformat() if project.updated_at else project.created_at.isoformat(),
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

    _doc_id = doc.id
    _proj_id = int(project_id)

    async def _ingest_with_own_session():
        from app.database import SessionLocal as _SL
        _db = _SL()
        try:
            await ingest_document(_doc_id, _proj_id, file_path, _db)
        except Exception:
            pass
        finally:
            _db.close()

    background_tasks.add_task(_ingest_with_own_session)

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


@router.post("/projects/{project_id}/pii-llm-filter")
async def pii_llm_filter(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """LLM quality-gate: prune false-positive NER detections.

    Fetches undecided NER (PERSON/ORG/GPE) detections, asks the LLM which
    are real human names or real company names, auto-overrides the rest.
    Returns {"candidates_sent": int, "kept": int, "pruned": int}.
    Safe fallback: if LLM call fails, all candidates are kept unchanged.
    """
    import re as _re
    from app.models.pii import PIIDetection
    from app.services.llm_factory import get_llm
    from app.services.pii_detection import decrypt_original

    _get_project_or_404(project_id, db)
    latest_doc = (
        db.query(Document)
        .filter(Document.project_id == int(project_id))
        .order_by(Document.upload_ts.desc())
        .first()
    )
    if not latest_doc:
        return {"candidates_sent": 0, "kept": 0, "pruned": 0}

    ner_dets = (
        db.query(PIIDetection)
        .filter(
            PIIDetection.document_id == latest_doc.id,
            PIIDetection.detection_method == "ner",
            PIIDetection.confirmed == False,   # noqa: E712
            PIIDetection.overridden == False,  # noqa: E712
        )
        .all()
    )
    if not ner_dets:
        return {"candidates_sent": 0, "kept": 0, "pruned": 0}

    candidates = [{"id": d.id, "text": decrypt_original(d.text_original)} for d in ner_dets]
    candidate_texts = [c["text"] for c in candidates]

    keep_texts: list[str] = list(candidate_texts)  # default: keep all (safe fallback)
    import time as _time
    from app.services.metrics_tracker import record_tokens, record_latency, calc_cost
    _t0 = _time.monotonic()
    try:
        llm = get_llm()
        prompt = (
            "You are a PII detection validator. These text spans were flagged by an NER model "
            "as possibly containing person names or organization names. Many are false positives "
            "(product names, generic terms, project labels, technology names, phase names).\n\n"
            f"Candidates: {json.dumps(candidate_texts)}\n\n"
            "Return ONLY candidates that are a REAL human full name (actual person's first+last name) "
            "or a REAL company/organization name (registered business, institution, team name). "
            'Respond with exactly: {"keep": ["...", "..."]} — no explanation, no markdown.'
        )
        resp = await llm.ainvoke([{"role": "user", "content": prompt}])
        raw = resp.content if hasattr(resp, "content") else str(resp)
        m = _re.search(r'\{[^}]*"keep"[^}]*\}', raw, _re.DOTALL)
        if m:
            parsed = json.loads(m.group())
            keep_texts = [t.strip() for t in parsed.get("keep", []) if isinstance(t, str)]
        usage = getattr(resp, "usage_metadata", None) or {}
        in_tok = int(usage.get("input_tokens", 0))
        out_tok = int(usage.get("output_tokens", 0))
        model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "unknown")
        record_tokens(int(project_id), "phase_1", model_name, in_tok, out_tok, calc_cost(in_tok, out_tok))
        record_latency(int(project_id), "phase_1", "pii_llm_filter", (_time.monotonic() - _t0) * 1000)
    except Exception:
        pass  # safe fallback: keep_texts already set to all candidates

    pruned = 0
    for det in ner_dets:
        text = decrypt_original(det.text_original)
        if text not in keep_texts:
            det.overridden = True
            pruned += 1
    db.commit()

    return {
        "candidates_sent": len(ner_dets),
        "kept": len(ner_dets) - pruned,
        "pruned": pruned,
    }


@router.get("/projects/{project_id}/document-status")
def get_document_status(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Return latest document status and project phase.

    Frontend polls this after PATCH /redaction-decisions to know when
    complete_ingestion() has finished (status == 'ready') before navigating.
    """
    project = _get_project_or_404(project_id, db)
    doc = (
        db.query(Document)
        .filter(Document.project_id == project.id)
        .order_by(Document.upload_ts.desc())
        .first()
    )
    return {
        "status": doc.status.value if doc else "none",
        "project_phase": project.phase.value,
    }


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

    # Prune trivial bare-keyword TBD rows left by older detection runs
    from app.services.tbd_detection import _BARE_KEYWORDS as _tbd_bare_kw
    stale = (
        db.query(Clarification)
          .filter(Clarification.project_id == pid, Clarification.level == TBDLevel.explicit)
          .all()
    )
    pruned = False
    for row in stale:
        if row.title.strip().rstrip(".").lower() in _tbd_bare_kw:
            db.delete(row)
            pruned = True
    if pruned:
        db.commit()

    tbds = (
        db.query(Clarification)
        .filter(Clarification.project_id == pid)
        .order_by(Clarification.status)
        .all()
    )
    return [
        TBDItem(
            id=str(t.id),
            question=t.title,
            level=_tbd_level_int.get(t.level, 1),
            resolved=t.status != TBDStatus.open,
            status=t.status.value if hasattr(t.status, "value") else str(t.status),
            source_sentence=t.source_sentence,
            source_section=t.source_section or None,
            source_page=t.source_page,
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
async def generate_proposal(
    project_id: str,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    project = _get_project_or_404(project_id, db)
    proposal = await _run_proposal_generation(project, db)
    return _proposal_to_response(proposal, project_id)


@router.post("/projects/{project_id}/proposal/stream")
async def generate_proposal_stream(
    project_id: str,
    db: Session = Depends(get_db),
):
    """SSE stream for initial proposal generation. Same events as retry/stream."""
    from app.services.proposal_generator import generate_structured_proposal_stream
    from fastapi.responses import StreamingResponse

    project = _get_project_or_404(project_id, db)

    async def _generate():
        sections = []
        async for section in generate_structured_proposal_stream(project, db):
            sections.append(section)
            payload = json.dumps({"type": "section", "section": section.model_dump(mode="json")})
            yield f"data: {payload}\n\n"

        proposal = _save_proposal_from_sections(project, db, sections)
        done_payload = json.dumps({
            "type": "done",
            "proposal": _proposal_to_response(proposal, project_id).model_dump(mode="json"),
        })
        yield f"data: {done_payload}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
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

    return _proposal_to_response(proposal, project_id)


@router.post("/projects/{project_id}/proposal/retry", response_model=ProposalResponse, status_code=201)
async def retry_proposal(
    project_id: str,
    body: ProposalRetryRequest,
    db: Session = Depends(get_db),
) -> ProposalResponse:
    project = _get_project_or_404(project_id, db)
    proposal = await _run_proposal_generation(project, db, extra_feedback=body.comment)
    return _proposal_to_response(proposal, project_id)


@router.post("/projects/{project_id}/proposal/retry/stream")
async def retry_proposal_stream(
    project_id: str,
    body: ProposalRetryRequest,
    db: Session = Depends(get_db),
):
    """SSE stream: emits each section as generated, then a done event with the full proposal."""
    from app.services.proposal_generator import generate_structured_proposal_stream
    from fastapi.responses import StreamingResponse

    project = _get_project_or_404(project_id, db)

    async def _generate():
        sections = []
        async for section in generate_structured_proposal_stream(project, db, body.comment):
            sections.append(section)
            payload = json.dumps({"type": "section", "section": section.model_dump(mode="json")})
            yield f"data: {payload}\n\n"

        proposal = _save_proposal_from_sections(project, db, sections)
        done_payload = json.dumps({
            "type": "done",
            "proposal": _proposal_to_response(proposal, project_id).model_dump(mode="json"),
        })
        yield f"data: {done_payload}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/proposal/approve", response_model=ProposalResponse)
def approve_proposal(
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
        raise HTTPException(status_code=404, detail="No proposal to approve")
    project.phase = ProjectPhase.modules
    db.commit()
    return _proposal_to_response(proposal, project_id)


@router.post(
    "/projects/{project_id}/proposal/sections/{section_id}/regenerate",
    response_model=SectionResponse,
)
async def regenerate_section(
    project_id: str,
    section_id: ProposalSectionId,
    body: RegenerateSectionRequest = None,
    db: Session = Depends(get_db),
) -> SectionResponse:
    from app.services.proposal_generator import generate_single_section

    if body is None:
        body = RegenerateSectionRequest()

    if section_id == ProposalSectionId.open_questions:
        raise HTTPException(status_code=400, detail="open_questions is read-only — cannot regenerate")

    project = _get_project_or_404(project_id, db)
    proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )
    if not proposal:
        raise HTTPException(status_code=404, detail="No proposal found for this project")
    if proposal.template_version != TEMPLATE_VERSION:
        raise HTTPException(
            status_code=400,
            detail=f"Proposal template_version mismatch: expected {TEMPLATE_VERSION}, got {proposal.template_version}",
        )

    updated_section = await generate_single_section(
        section_id, project, db, additional_context=body.additional_context
    )

    # Persist updated section back into sections_json
    if proposal.sections_json:
        try:
            raw = json.loads(proposal.sections_json)
            raw = [s for s in raw if s.get("section_id") != section_id.value]
            raw.append(updated_section.model_dump(mode="json"))
            # Re-sort to enum order
            order = [sid.value for sid in ProposalSectionId]
            raw.sort(key=lambda s: order.index(s["section_id"]) if s["section_id"] in order else 99)
            proposal.sections_json = json.dumps(raw)
            db.commit()
        except Exception:
            pass

    # Track token usage
    try:
        from app.services.metrics_tracker import record_tokens
        record_tokens(
            project_id=int(project_id),
            phase="proposal_section_regen",
            model="gpt-5.4-nano",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        )
    except Exception:
        pass

    return updated_section


# ── Modules endpoints ──────────────────────────────────────────────────────────

def _parse_modules(project: "Project") -> list[dict]:
    """Return parsed modules list from project.modules_json, or []."""
    if not project.modules_json:
        return []
    try:
        return json.loads(project.modules_json)
    except Exception:
        return []


@router.post("/projects/{project_id}/modules", response_model=ModulesResponse, status_code=201)
async def extract_modules(
    project_id: str,
    db: Session = Depends(get_db),
) -> ModulesResponse:
    """Extract high-level work modules from the approved proposal using LLM."""
    import uuid
    project = _get_project_or_404(project_id, db)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )

    sections_text = ""
    if proposal and proposal.content_json:
        try:
            raw = json.loads(proposal.content_json)
            sections = raw.get("sections", [])
            sections_text = "\n\n".join(
                f"## {s['heading']}\n{s['body']}" for s in sections
            )
        except Exception:
            pass

    modules: list[dict] = []
    if sections_text:
        prompt = (
            "You are a project analyst. Given this proposal, extract ALL discrete work modules.\n"
            "For each module output: title (concise noun phrase), label (one of: frontend, backend, "
            "devops, QA, PM, design, data, infra), description (one sentence).\n\n"
            f"Proposal sections:\n{sections_text}\n\n"
            'Respond ONLY with valid JSON:\n'
            '{"modules": [{"id": "<uuid4>", "title": "...", "label": "...", "description": "..."}, ...]}'
        )
        try:
            import time as _time
            from app.services.llm_factory import get_llm
            from app.services.metrics_tracker import calc_cost, record_latency, record_tokens
            t0 = _time.monotonic()
            result = await get_llm().ainvoke(prompt)
            elapsed_ms = (_time.monotonic() - t0) * 1000
            content = result.content if hasattr(result, "content") else str(result)
            # Extract token usage from response metadata if available
            usage = getattr(result, "response_metadata", {}).get("token_usage") or {}
            input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
            output_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0
            from app.config import settings as _settings
            record_tokens(
                int(project_id), "modules", _settings.main_llm_model,
                input_tokens, output_tokens, calc_cost(input_tokens, output_tokens),
            )
            record_latency(int(project_id), "modules", "module_extractor", elapsed_ms)
            # Strip markdown code fences if present
            content = re.sub(r"```(?:json)?\s*", "", content).strip().rstrip("```").strip()
            parsed = json.loads(content)
            for m in parsed.get("modules", []):
                modules.append({
                    "id": m.get("id") or str(uuid.uuid4()),
                    "title": str(m.get("title", "")),
                    "label": str(m.get("label", "backend")),
                    "description": str(m.get("description", "")),
                })
        except Exception:
            pass  # Safe fallback: return empty list

    project.modules_json = json.dumps(modules)
    db.commit()
    return ModulesResponse(modules=[ModuleOut(**m) for m in modules])


@router.post("/projects/{project_id}/modules/stream")
async def extract_modules_stream(
    project_id: str,
    db: Session = Depends(get_db),
):
    """SSE stream: emits status → module events → done for module extraction."""
    import uuid as _uuid
    from app.services.llm_factory import get_llm

    project = _get_project_or_404(project_id, db)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.project_id == project.id)
        .order_by(Proposal.created_at.desc())
        .first()
    )

    sections_text = ""
    if proposal and proposal.content_json:
        try:
            raw = json.loads(proposal.content_json)
            sections = raw.get("sections", [])
            sections_text = "\n\n".join(
                f"## {s['heading']}\n{s['body']}" for s in sections
            )
        except Exception:
            pass

    prompt = (
        "You are a project analyst. Given this proposal, extract ALL discrete work modules.\n"
        "For each module output: title (concise noun phrase), label (one of: frontend, backend, "
        "devops, QA, PM, design, data, infra), description (one sentence).\n\n"
        f"Proposal sections:\n{sections_text}\n\n"
        'Respond ONLY with valid JSON:\n'
        '{"modules": [{"id": "<uuid4>", "title": "...", "label": "...", "description": "..."}, ...]}'
    )

    llm = get_llm()
    from app.config import settings as _cfg
    _main_model = _cfg.main_llm_model

    async def _generate():
        import time as _time
        from app.services.metrics_tracker import calc_cost, record_latency, record_tokens
        yield f'data: {json.dumps({"type": "status", "status": "started"})}\n\n'

        buffer = ""
        full_buffer = ""
        seen_ids: set[str] = set()
        modules: list[dict] = []
        t0 = _time.monotonic()

        try:
            if sections_text:
                async for chunk in llm.astream(prompt):
                    token = chunk.content if hasattr(chunk, "content") else str(chunk)
                    buffer += token
                    full_buffer += token
                    matches = list(re.finditer(r'\{[^{}]+\}', buffer))
                    for match in matches:
                        try:
                            m = json.loads(match.group())
                            if {"title", "label"} <= m.keys() and m.get("title"):
                                mid = m.get("id") or str(_uuid.uuid4())
                                if mid not in seen_ids:
                                    seen_ids.add(mid)
                                    module = {
                                        "id": mid,
                                        "title": str(m["title"]),
                                        "label": str(m.get("label", "backend")),
                                        "description": str(m.get("description", "")),
                                    }
                                    modules.append(module)
                                    yield f'data: {json.dumps({"type": "module", "module": module})}\n\n'
                        except (json.JSONDecodeError, KeyError):
                            pass
                    if matches:
                        buffer = buffer[matches[-1].end():]

            # Fallback: parse full buffer to catch modules regex missed (e.g. full JSON in one chunk)
            if full_buffer.strip():
                try:
                    cleaned = re.sub(r"```(?:json)?\s*", "", full_buffer).strip().rstrip("`").strip()
                    parsed = json.loads(cleaned)
                    for m in parsed.get("modules", []):
                        if m.get("title") and m.get("label"):
                            mid = m.get("id") or str(_uuid.uuid4())
                            if mid not in seen_ids:
                                seen_ids.add(mid)
                                module = {
                                    "id": mid,
                                    "title": str(m["title"]),
                                    "label": str(m.get("label", "backend")),
                                    "description": str(m.get("description", "")),
                                }
                                modules.append(module)
                                yield f'data: {json.dumps({"type": "module", "module": module})}\n\n'
                except Exception:
                    pass

            elapsed_ms = (_time.monotonic() - t0) * 1000
            # Estimate tokens from full_buffer length (4 chars ≈ 1 token)
            est_output = max(1, len(full_buffer) // 4)
            est_input = max(1, len(prompt) // 4)
            record_tokens(
                int(project_id), "modules", _main_model,
                est_input, est_output, calc_cost(est_input, est_output),
            )
            record_latency(int(project_id), "modules", "module_extractor", elapsed_ms)
            yield f'data: {json.dumps({"type": "done", "modules": modules, "count": len(modules)})}\n\n'
        finally:
            project.modules_json = json.dumps(modules)
            db.commit()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/projects/{project_id}/modules", response_model=ModulesResponse)
def get_modules(
    project_id: str,
    db: Session = Depends(get_db),
) -> ModulesResponse:
    project = _get_project_or_404(project_id, db)
    modules = _parse_modules(project)
    return ModulesResponse(modules=[ModuleOut(**m) for m in modules])


@router.patch("/projects/{project_id}/modules", response_model=ModulesResponse)
def update_modules(
    project_id: str,
    body: ModulePatchRequest,
    db: Session = Depends(get_db),
) -> ModulesResponse:
    project = _get_project_or_404(project_id, db)
    project.modules_json = json.dumps([m.model_dump() for m in body.modules])
    db.commit()
    return ModulesResponse(modules=body.modules)


@router.post("/projects/{project_id}/modules/approve", response_model=ModulesResponse)
def approve_modules(
    project_id: str,
    db: Session = Depends(get_db),
) -> ModulesResponse:
    project = _get_project_or_404(project_id, db)
    if project.phase not in (ProjectPhase.modules, *_POST_MODULES_PHASES):
        raise HTTPException(
            status_code=409,
            detail="Project must be in modules phase to approve",
        )
    if project.phase == ProjectPhase.modules:
        project.phase = ProjectPhase.techstack
        db.commit()
    modules = _parse_modules(project)
    return ModulesResponse(modules=[ModuleOut(**m) for m in modules])


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


@router.get("/projects/{project_id}/export/estimate")
def export_estimate(
    project_id: str,
    format: str = "xlsx",
    db: Session = Depends(get_db),
):
    """Download the effort estimate as CSV or XLSX (Phase 5 must be complete)."""
    if format not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="format must be csv or xlsx")

    project = _get_project_or_404(project_id, db)
    if project.phase not in _POST_ESTIMATION_PHASES:
        raise HTTPException(status_code=409, detail="Phase 5 not complete")

    from app.services.estimate_export import build_estimate_csv, build_estimate_xlsx

    if format == "csv":
        buf = build_estimate_csv(project.id, db)
        return StreamingResponse(
            buf,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=estimate_{project_id}.csv"},
        )

    buf = build_estimate_xlsx(project.id, db)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=estimate_{project_id}.xlsx"},
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

    if project.phase not in _POST_MODULES_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 3 (modules) must be complete before running tech stack suggestion",
        )

    # Return cached result if tech stack already ran
    cached = project.tech_stack or {}
    if cached and project.phase in _POST_STACK_PHASES:
        return TechStackResponse(
            frontend=cached.get("frontend", []),
            backend=cached.get("backend", []),
            database=cached.get("database", []),
            infra=cached.get("infra", []),
            rationale=cached.get("rationale", ""),
        )

    tech_stack: dict = {}
    try:
        from app.services.workflow import run_phase
        # Ensure chat_proceed=True so the workflow exits the chat loop on resume
        state = await run_phase(str(project.id), state_update={"chat_proceed": True})
        tech_stack = state.get("tech_stack") or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Tech stack suggestion failed: {exc}") from exc

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


@router.get("/projects/{project_id}/stack", response_model=None)
def get_stack(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Return cached tech stack or 204 if not yet generated."""
    project = _get_project_or_404(project_id, db)
    cached = project.tech_stack or {}
    if not cached:
        return Response(status_code=204)
    return TechStackResponse(
        frontend=cached.get("frontend", []),
        backend=cached.get("backend", []),
        database=cached.get("database", []),
        infra=cached.get("infra", []),
        rationale=cached.get("rationale", ""),
    )


@router.post("/projects/{project_id}/stack/stream")
async def suggest_stack_stream(
    project_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """SSE stream: emits status → category events → rationale → done for tech stack generation."""
    from app.services.llm_factory import get_llm
    from app.models.reference import ApprovedTechnology

    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_MODULES_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 3 (modules) must be complete before running tech stack suggestion",
        )

    cached = project.tech_stack or {}
    if not force and cached and project.phase in _POST_STACK_PHASES:
        async def _cached_gen():
            yield f'data: {json.dumps({"type": "status", "message": "Loading cached stack..."})}\n\n'
            for key in ("frontend", "backend", "database", "infra"):
                yield f'data: {json.dumps({"type": "category", "key": key, "items": cached.get(key, [])})}\n\n'
            if cached.get("rationale"):
                yield f'data: {json.dumps({"type": "rationale", "text": cached["rationale"]})}\n\n'
            yield f'data: {json.dumps({"type": "done", "stack": cached})}\n\n'

        return StreamingResponse(
            _cached_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    techs = db.query(ApprovedTechnology).all()
    tech_descriptions = "\n".join(
        f"- {t.name} ({t.category}): {t.tags or ''}" for t in techs
    ) or "No approved technologies in database."

    proposal_sections: dict = {}
    try:
        proposal = (
            db.query(Proposal)
            .filter(Proposal.project_id == project.id)
            .order_by(Proposal.id.desc())
            .first()
        )
        if proposal and proposal.sections_json:
            for s in json.loads(proposal.sections_json):
                proposal_sections[s["section_id"]] = s
    except Exception:
        pass

    _SECTION_KEYS = ("overview", "technical_requirements", "key_features", "problem_statement")
    section_parts = []
    for k in _SECTION_KEYS:
        sec = proposal_sections.get(k) or {}
        title = sec.get("title") or k.replace("_", " ").title()
        content = sec.get("content", "").strip()
        if content:
            section_parts.append(f"### {title}\n{content}")
    proposal_summary = "\n\n".join(section_parts) if section_parts else "No proposal context available."

    prompt = (
        f"Given this project proposal:\n{proposal_summary}\n\n"
        "Select technologies ONLY from the approved list below. "
        "Do not suggest any technology not present in this list. Use EXACT names as written.\n\n"
        f"{tech_descriptions}\n\n"
        "Choose 1-3 per category (frontend, backend, database, infra). "
        "Use the tags to match project needs — e.g. prefer 'prototyping' tags for MVPs, "
        "'high-scale' for enterprise. "
        "Respond ONLY with valid JSON (no markdown, no explanation outside the JSON):\n"
        '{"frontend": [...], "backend": [...], "database": [...], "infra": [...], "rationale": "..."}'
    )

    llm = get_llm(fast=False)

    async def _generate():
        import time as _t
        yield f'data: {json.dumps({"type": "status", "message": "Analyzing requirements..."})}\n\n'

        buffer = ""
        full_buffer = ""
        emitted_keys: set[str] = set()
        tech_stack: dict = {}
        _t0 = _t.time()

        try:
            async for chunk in llm.astream(prompt):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                buffer += token
                full_buffer += token

                last_match_end = 0
                for key in ("frontend", "backend", "database", "infra"):
                    if key in emitted_keys:
                        continue
                    m = re.search(rf'"{key}":\s*(\[[^\]]*\])', buffer)
                    if m:
                        try:
                            items = json.loads(m.group(1))
                            if isinstance(items, list):
                                emitted_keys.add(key)
                                tech_stack[key] = items
                                yield f'data: {json.dumps({"type": "category", "key": key, "items": items})}\n\n'
                                last_match_end = max(last_match_end, m.end())
                        except json.JSONDecodeError:
                            pass
                if last_match_end > 0:
                    buffer = buffer[last_match_end:]

                if "rationale" not in emitted_keys:
                    m = re.search(r'"rationale":\s*"((?:[^"\\]|\\.)*)"', buffer)
                    if m:
                        try:
                            rationale = json.loads(f'"{m.group(1)}"')
                            emitted_keys.add("rationale")
                            tech_stack["rationale"] = rationale
                            yield f'data: {json.dumps({"type": "rationale", "text": rationale})}\n\n'
                        except json.JSONDecodeError:
                            pass

            # Fallback: parse full buffer for keys the regex missed
            if len(emitted_keys) < 5:
                try:
                    cleaned = re.sub(r"```(?:json)?\s*", "", full_buffer).strip().rstrip("`").strip()
                    parsed = json.loads(cleaned)
                    for key in ("frontend", "backend", "database", "infra"):
                        if key not in emitted_keys and isinstance(parsed.get(key), list):
                            tech_stack[key] = parsed[key]
                            yield f'data: {json.dumps({"type": "category", "key": key, "items": parsed[key]})}\n\n'
                    if "rationale" not in emitted_keys and isinstance(parsed.get("rationale"), str):
                        tech_stack["rationale"] = parsed["rationale"]
                        yield f'data: {json.dumps({"type": "rationale", "text": parsed["rationale"]})}\n\n'
                except Exception:
                    pass

            yield f'data: {json.dumps({"type": "done", "stack": tech_stack})}\n\n'

            try:
                from app.services.metrics_tracker import record_tokens, record_latency, calc_cost
                from app.config import settings as _settings
                _in = llm.get_num_tokens(prompt)
                _out = llm.get_num_tokens(full_buffer)
                record_tokens(int(project_id), "phase_3", _settings.main_llm_model, _in, _out, calc_cost(_in, _out))
                record_latency(int(project_id), "phase_3", "suggest_stack_stream", (_t.time() - _t0) * 1000)
            except Exception:
                pass

        finally:
            if tech_stack:
                with SessionLocal() as _db:
                    _proj = _db.query(Project).filter(Project.id == int(project_id)).first()
                    if _proj:
                        _proj.tech_stack = tech_stack
                        _db.commit()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/team", response_model=TeamResponse)
async def suggest_team(
    project_id: str,
    db: Session = Depends(get_db),
) -> TeamResponse:
    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_STACK_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 3 (tech stack suggestion) must be complete before running team suggestion",
        )

    # Return cached result only when AI already ran with a real tech stack.
    # A cached result with technologies=[] means AI ran with empty tech stack —
    # don't trust it; re-run with the correct data.
    cached = project.team_suggestion or {}
    has_valid_cache = (
        bool(cached.get("technologies")) and
        bool(cached.get("members")) and  # empty members = prior bug run, re-run
        project.phase in _POST_TEAM_PHASES
    )
    if has_valid_cache:
        members = cached.get("members", [])
        return TeamResponse(members=members, total=len(members))

    # Bypass run_phase: phase 3 is often run via the streaming endpoint which
    # saves to project.tech_stack (app.db) but NOT to the LangGraph checkpoint.
    # run_phase always starts fresh at phase 2 chat and never reaches phase 4.
    # We call _suggest_team_direct instead to skip LangGraph entirely.
    try:
        from app.services.workflow import suggest_team_direct
        team = suggest_team_direct(project.tech_stack or {})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Team suggestion failed: {exc}") from exc

    project.team_suggestion = team
    if project.phase == ProjectPhase.techstack:
        project.phase = ProjectPhase.team
    db.commit()

    members = team.get("members", [])
    return TeamResponse(members=members, total=len(members))


@router.put("/projects/{project_id}/team", status_code=200)
async def update_team(
    project_id: str,
    body: TeamUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    """Persist PM-confirmed team (AI-suggested + manually added) and sync LangGraph state."""
    project = _get_project_or_404(project_id, db)
    existing = project.team_suggestion or {}
    team = {
        "members": body.members,
        "technologies": existing.get("technologies", []),
    }
    project.team_suggestion = team
    db.commit()

    # Sync LangGraph checkpoint so estimation node picks up the confirmed team
    try:
        wf = await get_workflow()
        config = {"configurable": {"thread_id": str(project.id)}}
        await wf.aupdate_state(config, {"team_suggestion": team})
    except Exception:
        pass

    return {"status": "ok", "total": len(body.members)}


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

    # Return cached result if estimation already ran
    cached = project.effort_estimates or {}
    if cached and project.phase in _POST_ESTIMATION_PHASES:
        cached_confidence = cached.get("confidence", 0.7)
        cached_breakdown = cached.get("breakdown", {})
        cached_epics = cached.get("epics") or [
            {"title": p.replace("_", " ").title(), "estimated_points": pts, "confidence": cached_confidence}
            for p, pts in cached_breakdown.items()
        ]
        return EstimationResponse(
            epics=cached_epics,
            total_points=cached.get("total_points", 0),
            total_weeks=cached.get("total_weeks", 0),
        )

    effort: dict = {}
    try:
        from app.services.workflow import run_phase
        state = await run_phase(str(project.id))
        effort = state.get("effort_estimates") or {}
        for _ in range(6):
            if effort:
                break
            state = await run_phase(str(project.id))
            effort = state.get("effort_estimates") or {}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Effort estimation failed: {exc}") from exc

    project.effort_estimates = effort
    db.commit()

    if project.phase == ProjectPhase.team:
        project.phase = ProjectPhase.estimation
        db.commit()

    confidence = effort.get("confidence", 0.7)
    breakdown = effort.get("breakdown", {})
    breakdown_epics = [
        {"title": phase.replace("_", " ").title(), "estimated_points": pts, "confidence": confidence}
        for phase, pts in breakdown.items()
    ] if breakdown else []

    return EstimationResponse(
        epics=effort.get("epics") or breakdown_epics or [],
        total_points=effort.get("total_points", 0),
        total_weeks=effort.get("total_weeks", 0.0),
    )


@router.post("/projects/{project_id}/estimate/stream")
async def estimate_effort_stream(
    project_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """SSE stream: status → epic events (one per breakdown phase) → summary → done."""
    from app.services.llm_factory import get_llm
    from app.models.reference import HistoricalProject

    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_TEAM_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 4 (team suggestion) must be complete before running effort estimation",
        )

    cached = project.effort_estimates or {}
    if not force and cached and project.phase in _POST_ESTIMATION_PHASES:
        async def _cached_gen():
            yield f'data: {json.dumps({"type": "status", "message": "Loading cached estimation..."})}\n\n'
            breakdown = cached.get("breakdown", {})
            epics = []
            if isinstance(breakdown, dict):
                for phase_name, pts in breakdown.items():
                    epic = {"title": phase_name, "estimated_points": int(pts)}
                    epics.append(epic)
                    yield f'data: {json.dumps({"type": "epic", **epic})}\n\n'
            elif isinstance(breakdown, list):
                for item in breakdown:
                    if isinstance(item, dict):
                        epic = {"title": item.get("phase", ""), "estimated_points": int(item.get("points", 0))}
                        epics.append(epic)
                        yield f'data: {json.dumps({"type": "epic", **epic})}\n\n'
            yield f'data: {json.dumps({"type": "summary", "total_points": cached.get("total_points", 0), "total_weeks": cached.get("total_weeks", 0), "confidence": cached.get("confidence", 0.7), "reasoning": cached.get("reasoning", "")})}\n\n'
            yield f'data: {json.dumps({"type": "done", "epics": epics, "total_points": int(cached.get("total_points", 0)), "total_weeks": float(cached.get("total_weeks", 0))})}\n\n'

        return StreamingResponse(
            _cached_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Build proposal summary (same approach as stack/stream)
    proposal_sections: dict = {}
    try:
        proposal = (
            db.query(Proposal)
            .filter(Proposal.project_id == project.id)
            .order_by(Proposal.id.desc())
            .first()
        )
        if proposal and proposal.sections_json:
            for s in json.loads(proposal.sections_json):
                proposal_sections[s["section_id"]] = s
    except Exception:
        pass

    _SECTION_KEYS = ("overview", "technical_requirements", "key_features", "problem_statement")
    section_parts = []
    for k in _SECTION_KEYS:
        sec = proposal_sections.get(k) or {}
        title = sec.get("title") or k.replace("_", " ").title()
        content = sec.get("content", "").strip()
        if content:
            section_parts.append(f"### {title}\n{content}")
    proposal_summary = "\n\n".join(section_parts) if section_parts else "No proposal context available."

    team_suggestion = project.team_suggestion or {}
    team_size = len(team_suggestion.get("members", [])) or 3

    modules_text = ""
    try:
        if project.modules_json:
            mods = json.loads(project.modules_json)
            if mods:
                modules_text = "\n\nModules breakdown:\n" + json.dumps(
                    [{"title": m["title"], "label": m["label"]} for m in mods], indent=2
                )
    except Exception:
        pass

    async def _generate():
        import time as _t
        _t0 = _t.time()
        yield f'data: {json.dumps({"type": "status", "message": "Fetching historical projects..."})}\n\n'

        try:
            hist = db.query(HistoricalProject).limit(10).all()
            refs = "\n".join(
                f"- {p.name}: {p.duration_weeks or '?'}w, {p.team_size or '?'} devs, {p.estimated_points or '?'} pts"
                for p in hist
            ) or "No reference projects available."
        except Exception:
            refs = "No reference projects available."

        yield f'data: {json.dumps({"type": "status", "message": "Analyzing requirements and computing estimates..."})}\n\n'

        prompt = (
            f"Estimate effort for this project:\n{proposal_summary}"
            f"{modules_text}\n\n"
            f"Team size: {team_size}\n\n"
            f"Reference projects:\n{refs}\n\n"
            "Return ONLY valid JSON with these exact fields:\n"
            '{"total_weeks": <int>, "total_points": <int>, "confidence": <float 0.0-1.0>, '
            '"breakdown": [{"phase": "<name>", "points": <int>}, ...], "reasoning": "<explanation>"}'
        )

        llm = get_llm(fast=True)
        buffer = ""
        full_buffer = ""
        emitted_phases: set[str] = set()
        epics: list[dict] = []
        total_weeks = 0
        total_points = 0
        confidence = 0.7
        reasoning = ""

        try:
            async for chunk in llm.astream(prompt):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                buffer += token
                full_buffer += token

                last_end = 0
                for m in re.finditer(r'\{"phase":\s*"([^"]+)",\s*"points":\s*(\d+)\}', buffer):
                    phase_name = m.group(1)
                    points = int(m.group(2))
                    if phase_name not in emitted_phases:
                        emitted_phases.add(phase_name)
                        epic = {"title": phase_name, "estimated_points": points}
                        epics.append(epic)
                        yield f'data: {json.dumps({"type": "epic", **epic})}\n\n'
                    last_end = m.end()
                if last_end > 0:
                    buffer = buffer[last_end:]

            # Parse full buffer for summary fields + catch any missed breakdown items
            try:
                cleaned = re.sub(r"```(?:json)?\s*", "", full_buffer).strip().rstrip("`").strip()
                parsed = json.loads(cleaned)
                total_weeks = int(parsed.get("total_weeks", 0))
                total_points = int(parsed.get("total_points", 0))
                confidence = float(parsed.get("confidence", 0.7))
                reasoning = str(parsed.get("reasoning", ""))
                for item in parsed.get("breakdown", []):
                    if isinstance(item, dict):
                        phase_name = item.get("phase", "")
                        points = int(item.get("points", 0))
                        if phase_name and phase_name not in emitted_phases:
                            emitted_phases.add(phase_name)
                            epic = {"title": phase_name, "estimated_points": points}
                            epics.append(epic)
                            yield f'data: {json.dumps({"type": "epic", **epic})}\n\n'
            except Exception:
                m_weeks = re.search(r'"total_weeks":\s*(\d+)', full_buffer)
                if m_weeks:
                    total_weeks = int(m_weeks.group(1))
                m_points = re.search(r'"total_points":\s*(\d+)', full_buffer)
                if m_points:
                    total_points = int(m_points.group(1))
                m_conf = re.search(r'"confidence":\s*([\d.]+)', full_buffer)
                if m_conf:
                    confidence = min(1.0, max(0.0, float(m_conf.group(1))))
                m_reasoning = re.search(r'"reasoning":\s*"((?:[^"\\]|\\.)*)"', full_buffer)
                if m_reasoning:
                    try:
                        reasoning = json.loads(f'"{m_reasoning.group(1)}"')
                    except Exception:
                        reasoning = m_reasoning.group(1)

            yield f'data: {json.dumps({"type": "summary", "total_points": total_points, "total_weeks": total_weeks, "confidence": confidence, "reasoning": reasoning})}\n\n'
            yield f'data: {json.dumps({"type": "done", "epics": epics, "total_points": total_points, "total_weeks": float(total_weeks)})}\n\n'

            try:
                from app.services.metrics_tracker import record_tokens, record_latency, calc_cost
                from app.config import settings as _settings
                _in = llm.get_num_tokens(prompt)
                _out = llm.get_num_tokens(full_buffer)
                record_tokens(int(project_id), "phase_5", _settings.fast_llm_model, _in, _out, calc_cost(_in, _out))
                record_latency(int(project_id), "phase_5", "estimate_effort_stream", (_t.time() - _t0) * 1000)
            except Exception:
                pass

        finally:
            if epics or total_points:
                breakdown_dict = {e["title"]: e["estimated_points"] for e in epics}
                with SessionLocal() as _db:
                    _proj = _db.query(Project).filter(Project.id == int(project_id)).first()
                    if _proj:
                        _proj.effort_estimates = {
                            "total_weeks": total_weeks,
                            "total_points": total_points,
                            "confidence": confidence,
                            "breakdown": breakdown_dict,
                            "reasoning": reasoning,
                        }
                        if _proj.phase == ProjectPhase.team:
                            _proj.phase = ProjectPhase.estimation
                        _db.commit()

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/projects/{project_id}/epics")
async def generate_epics(
    project_id: str,
    db: Session = Depends(get_db),
) -> dict:
    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_ESTIMATION_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 5 (effort estimation) must be complete before generating epics",
        )

    epics_data: list = []
    try:
        from app.services.workflow import run_phase
        state = await run_phase(str(project.id))
        epics_data = state.get("epics") or []
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Epic generation failed: {exc}") from exc

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


@router.post("/projects/{project_id}/epics/stream")
async def stream_epics(
    project_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
):
    """SSE stream: status → epic events (one per epic+tasks) → done.

    Cache path: if epics already exist in DB and force=False, replays them instantly.
    Fresh path: calls LLM directly (bypasses ReAct loop), uses bracket-depth tracking
    to emit one 'epic' SSE event per complete JSON object as tokens arrive.
    DB persist happens BEFORE the 'done' event so getEpics() works immediately after.
    """
    import json as _json_mod
    from datetime import date
    from app.services.llm_factory import get_llm
    from app.services.workflow import _EPIC_GENERATION_PROMPT

    project = _get_project_or_404(project_id, db)

    if project.phase not in _POST_ESTIMATION_PHASES:
        raise HTTPException(
            status_code=409,
            detail="Phase 5 (effort estimation) must be complete before generating epics",
        )

    # ── Cache path ──────────────────────────────────────────────────────────
    existing_epics = db.query(Epic).filter(Epic.project_id == int(project_id)).all()
    if not force and existing_epics:
        async def _cached_gen():
            yield f'data: {json.dumps({"type": "status", "message": "Loading cached epics..."})}\n\n'
            for epic in existing_epics:
                tasks_data = []
                for t in epic.tasks:
                    try:
                        labels = _json_mod.loads(t.labels) if t.labels else []
                    except Exception:
                        labels = []
                    tasks_data.append({
                        "title": t.title,
                        "description": t.description or "",
                        "story_points": t.estimated_points or 3,
                        "labels": labels,
                    })
                yield f'data: {json.dumps({"type": "epic", "title": epic.title, "description": epic.description or "", "due_date": "", "tasks": tasks_data})}\n\n'
            yield f'data: {json.dumps({"type": "done", "count": len(existing_epics)})}\n\n'

        return StreamingResponse(
            _cached_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ── Build prompt context ────────────────────────────────────────────────
    proposal_sections: dict = {}
    try:
        proposal = (
            db.query(Proposal)
            .filter(Proposal.project_id == project.id)
            .order_by(Proposal.id.desc())
            .first()
        )
        if proposal and proposal.sections_json:
            for s in json.loads(proposal.sections_json):
                proposal_sections[s["section_id"]] = s
    except Exception:
        pass

    _SECTION_KEYS = ("overview", "technical_requirements", "key_features", "problem_statement")
    section_parts = []
    for k in _SECTION_KEYS:
        sec = proposal_sections.get(k) or {}
        title = sec.get("title") or k.replace("_", " ").title()
        content = sec.get("content", "").strip()
        if content:
            section_parts.append(f"### {title}\n{content}")
    proposal_summary = "\n\n".join(section_parts) if section_parts else "No proposal context available."

    tech_stack = project.tech_stack or {}
    tech_stack_summary = (
        ", ".join(
            tech_stack.get("frontend", [])
            + tech_stack.get("backend", [])
            + tech_stack.get("database", [])
            + tech_stack.get("infra", [])
        )
        or "Standard web stack"
    )
    today = date.today().isoformat()

    # ── Fresh generation ────────────────────────────────────────────────────
    async def _generate():
        import time as _t
        _t0 = _t.time()
        yield f'data: {json.dumps({"type": "status", "message": "Generating epics and tasks..."})}\n\n'

        prompt = (
            _EPIC_GENERATION_PROMPT.format(
                proposal_summary=proposal_summary,
                tech_stack_summary=tech_stack_summary,
                today=today,
            )
            + "\n\nReturn ONLY a valid JSON array of epic objects."
            " Each epic: {title, description, due_date, tasks: [{title, description, story_points, labels}]}."
            " No markdown fences, no explanation."
        )

        llm = get_llm(fast=False)
        full_buffer = ""
        epics: list[dict] = []

        # Bracket-depth tracking: detect complete top-level JSON objects inside the array.
        # Handles nested objects (tasks array) without regex.
        # Tracks string context to ignore structural chars inside string values.
        array_started = False
        brace_depth = 0
        current_epic = ""
        in_string = False
        escape_next = False

        async for chunk in llm.astream(prompt):
            token = chunk.content if hasattr(chunk, "content") else str(chunk)
            full_buffer += token

            for char in token:
                if escape_next:
                    escape_next = False
                    if brace_depth > 0:
                        current_epic += char
                    continue
                if char == "\\" and in_string:
                    escape_next = True
                    if brace_depth > 0:
                        current_epic += char
                    continue
                if char == '"':
                    in_string = not in_string
                    if brace_depth > 0:
                        current_epic += char
                    continue
                if in_string:
                    if brace_depth > 0:
                        current_epic += char
                    continue
                # Structural chars (not inside a string)
                if not array_started:
                    if char == "[":
                        array_started = True
                    continue
                if brace_depth == 0 and char == "{":
                    current_epic = "{"
                    brace_depth = 1
                elif brace_depth > 0:
                    current_epic += char
                    if char == "{":
                        brace_depth += 1
                    elif char == "}":
                        brace_depth -= 1
                        if brace_depth == 0:
                            try:
                                obj = json.loads(current_epic)
                                if "title" in obj:
                                    epic_event = {
                                        "title": obj["title"],
                                        "description": obj.get("description", ""),
                                        "due_date": obj.get("due_date", ""),
                                        "tasks": obj.get("tasks", []),
                                    }
                                    epics.append(epic_event)
                                    yield f'data: {json.dumps({"type": "epic", **epic_event})}\n\n'
                            except Exception:
                                pass
                            current_epic = ""

        # Fallback: parse full buffer if bracket tracking caught nothing
        if not epics:
            try:
                cleaned = re.sub(r"```(?:json)?\s*", "", full_buffer).strip().rstrip("`").strip()
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    for obj in parsed:
                        if isinstance(obj, dict) and "title" in obj:
                            epic_event = {
                                "title": obj["title"],
                                "description": obj.get("description", ""),
                                "due_date": obj.get("due_date", ""),
                                "tasks": obj.get("tasks", []),
                            }
                            epics.append(epic_event)
                            yield f'data: {json.dumps({"type": "epic", **epic_event})}\n\n'
            except Exception:
                pass

        # ── Persist BEFORE done event so getEpics() works immediately ───────
        if epics:
            with SessionLocal() as _db:
                if force:
                    old_ids = [
                        row[0]
                        for row in _db.query(Epic.id).filter(Epic.project_id == int(project_id)).all()
                    ]
                    if old_ids:
                        _db.query(Task).filter(Task.epic_id.in_(old_ids)).delete(
                            synchronize_session=False
                        )
                        _db.query(Epic).filter(Epic.project_id == int(project_id)).delete(
                            synchronize_session=False
                        )
                        _db.flush()

                for epic_dict in epics:
                    epic_orm = Epic(
                        project_id=int(project_id),
                        title=epic_dict["title"],
                        description=epic_dict.get("description", ""),
                        sync_status="pending",
                    )
                    _db.add(epic_orm)
                    _db.flush()
                    for task_dict in epic_dict.get("tasks", []):
                        _db.add(
                            Task(
                                epic_id=epic_orm.id,
                                title=task_dict.get("title", ""),
                                description=task_dict.get("description", ""),
                                estimated_points=task_dict.get("story_points", 3),
                                labels=json.dumps(task_dict.get("labels", [])),
                                sync_status="pending",
                            )
                        )
                _db.commit()

                _proj = _db.query(Project).filter(Project.id == int(project_id)).first()
                if _proj and _proj.phase == ProjectPhase.estimation:
                    _proj.phase = ProjectPhase.epics
                    _db.commit()

        try:
            from app.services.metrics_tracker import record_tokens, record_latency, calc_cost
            from app.config import settings as _settings
            _in = llm.get_num_tokens(prompt)
            _out = llm.get_num_tokens(full_buffer)
            record_tokens(int(project_id), "phase_6", _settings.main_llm_model, _in, _out, calc_cost(_in, _out))
            record_latency(int(project_id), "phase_6", "stream_epics", (_t.time() - _t0) * 1000)
        except Exception:
            pass

        yield f'data: {json.dumps({"type": "done", "count": len(epics)})}\n\n'

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
    body: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db),
) -> SyncResponse:
    import inspect
    import json as _json_mod
    from app.config import settings as _settings
    from app.models.enums import SyncStatus as DBSyncStatus
    from app.services.sync_factory import get_sync_fn

    project = _get_project_or_404(project_id, db)
    all_epics = db.query(Epic).filter(Epic.project_id == int(project_id)).all()
    if body.epic_ids is not None:
        epics = [e for e in all_epics if e.id in body.epic_ids]
    else:
        epics = all_epics

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

    try:
        provider, _config, sync_fn = get_sync_fn(project)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync configuration error: {exc}") from exc

    try:
        if inspect.iscoroutinefunction(sync_fn):
            result = await sync_fn(epics_payload)
        else:
            result = sync_fn(epics_payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Sync failed: {exc}") from exc

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

    milestones_url: str | None = None
    for ed in epics_payload:
        mu = ed.get("_milestone_url", "")
        if mu:
            import re as _re
            m = _re.match(r"(https://github\.com/[^/]+/[^/]+)/milestones?/\d+", mu)
            if m:
                milestones_url = m.group(1) + "/milestones"
            break

    return SyncResponse(**result, milestones_url=milestones_url)


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


@router.get(
    "/projects/{project_id}/chat-history",
    summary="Return persisted chat messages for this project",
)
async def get_chat_history(project_id: str) -> list[dict]:
    wf = await get_workflow()
    config = {"configurable": {"thread_id": project_id}}
    existing = await wf.aget_state(config)
    return list(existing.values.get("chat_messages") or [])


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

    # Layer 0: prompt injection — regex (fast) then LLM semantic (catches obfuscation/synonyms)
    from app.config import settings as _cfg_inj
    if _cfg_inj.prompt_injection_detection_enabled:
        from app.guardrails.prompt_injection import classify_llm as _inj_llm
        from app.guardrails.prompt_injection import scan as _inj_scan
        from app.guardrails import log_guardrail as _log_guardrail
        _inj = _inj_scan(body.message)
        if not _inj.detected:
            _inj = await _inj_llm(body.message, project_id)
        if _inj.detected:
            if _inj.pattern != "llm_semantic":  # llm path logs inside classify_llm
                _log_guardrail(project_id, 0, "injection_detected", None,
                               {"pattern": _inj.pattern, "matched": _inj.matched_text})
            raise HTTPException(status_code=400, detail="Message contains disallowed content.")

    # Layer 1: domain classification — raises HTTP 400 if clearly non-PM with high confidence
    from app.guardrails.domain_classifier import classify as _domain_classify
    await _domain_classify(body.message, project_id)

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

                    # Layer 2: gate blocked — stream gate message instead of LLM response
                    gate_status = output.get("gate_status")
                    if gate_status and gate_status != "pass":
                        yield f"data: {json.dumps({'type': 'gate_blocked', 'status': gate_status, 'message': output.get('gate_message')})}\n\n"

                    if tbds := output.get("tbd_items"):
                        yield f"data: {json.dumps({'type': 'tbds', 'items': tbds})}\n\n"

                    if sources := output.get("retrieved_sources"):
                        yield f"data: {json.dumps({'type': 'sources', 'items': sources})}\n\n"

                    # Layer 3: groundedness events
                    gs = output.get("groundedness_score")
                    if gs is not None:
                        from app.config import settings as _cfg
                        flagged = gs < _cfg.groundedness_threshold
                        yield f"data: {json.dumps({'type': 'groundedness', 'score': gs, 'flagged': flagged})}\n\n"
                        if flagged:
                            yield f"data: {json.dumps({'type': 'groundedness_warning', 'score': gs, 'unsupported_claims': output.get('groundedness_unsupported_claims') or [], 'reasoning': output.get('groundedness_reasoning') or '', 'source': 'general_knowledge' if output.get('groundedness_unsupported_claims') else None})}\n\n"

                    # Layer 4: canary token leak — possible system prompt exfiltration
                    if output.get("canary_leaked"):
                        yield f"data: {json.dumps({'type': 'canary_leaked', 'message': 'Possible system prompt exfiltration detected. Response has been flagged.'})}\n\n"

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
    from sqlalchemy import func

    from app.models.enums import SyncStatus
    from app.models.observability import (
        ErrorLog, EvalResult, LatencyLog, Metric, QualityLog, RetrievalLog
    )
    from app.models.sync import Epic, Task
    from app.schemas.metrics import (
        DailyTokenItem, ErrorPhaseItem, LatencyNodeItem,
        QualityScoreItem, RetrievalQueryItem, TokenPhaseItem,
    )

    _get_project_or_404(project_id, db)
    pid = int(project_id)

    # ── Token aggregation ──────────────────────────────────────────────────────
    metric_rows = db.query(Metric).filter(Metric.project_id == pid).all()
    total_input = sum(r.input_tokens for r in metric_rows)
    total_output = sum(r.output_tokens for r in metric_rows)
    total_tokens = total_input + total_output
    total_cost = sum(r.cost_usd for r in metric_rows)

    phase_token_map: dict[str, dict] = {}
    for r in metric_rows:
        e = phase_token_map.setdefault(r.phase, {"tokens": 0, "cost": 0.0})
        e["tokens"] += r.input_tokens + r.output_tokens
        e["cost"] += r.cost_usd

    # ── Daily token trend ──────────────────────────────────────────────────────
    daily_rows = (
        db.query(
            func.date(Metric.created_at).label("day"),
            func.sum(Metric.input_tokens).label("inp"),
            func.sum(Metric.output_tokens).label("out"),
            func.sum(Metric.cost_usd).label("cost"),
        )
        .filter(Metric.project_id == pid)
        .group_by(func.date(Metric.created_at))
        .order_by(func.date(Metric.created_at))
        .all()
    )
    daily_token_trend = [
        DailyTokenItem(
            day=str(r.day),
            input_tokens=int(r.inp or 0),
            output_tokens=int(r.out or 0),
            cost=round(float(r.cost or 0), 6),
        )
        for r in daily_rows
    ]

    # ── Latency aggregation (p50/p95 per node) ─────────────────────────────────
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

    # ── Error aggregation per phase ────────────────────────────────────────────
    error_rows = db.query(ErrorLog).filter(ErrorLog.project_id == pid).all()
    phase_error_map: dict[str, int] = {}
    for r in error_rows:
        phase_error_map[r.phase or "unknown"] = phase_error_map.get(r.phase or "unknown", 0) + 1

    # ── GitHub sync rate ───────────────────────────────────────────────────────
    epic_rows = db.query(Epic).filter(Epic.project_id == pid).all()
    task_rows = (
        db.query(Task)
        .join(Epic, Task.epic_id == Epic.id)
        .filter(Epic.project_id == pid)
        .all()
    )
    all_sync_items = epic_rows + task_rows
    synced_count = sum(1 for r in all_sync_items if r.sync_status == SyncStatus.synced)
    failed_count = sum(1 for r in all_sync_items if r.sync_status == SyncStatus.failed)
    github_sync_success_rate = synced_count / len(all_sync_items) if all_sync_items else 1.0

    # ── Retrieval quality ──────────────────────────────────────────────────────
    retrieval_rows = (
        db.query(RetrievalLog)
        .filter(RetrievalLog.project_id == pid)
        .order_by(RetrievalLog.query_index)
        .all()
    )
    retrieval_by_query = [
        RetrievalQueryItem(
            query_index=r.query_index,
            n_retrieved=r.n_retrieved,
            top_score=round(float(r.top_score), 4),
            avg_score=round(float(r.avg_score), 4),
        )
        for r in retrieval_rows
    ]

    # ── Quality scores (live groundedness + eval run scores) ───────────────────
    quality_rows = db.query(QualityLog).filter(QualityLog.project_id == pid).all()
    groundedness_scores = [r.score for r in quality_rows if r.score_type == "groundedness"]
    avg_groundedness = (
        round(sum(groundedness_scores) / len(groundedness_scores), 4)
        if groundedness_scores else None
    )

    quality_scores: list[QualityScoreItem] = []
    if avg_groundedness is not None:
        quality_scores.append(QualityScoreItem(grader="groundedness", score=avg_groundedness, source="live"))

    # Latest eval run
    eval_pass_rate = 0.0
    latest_run = (
        db.query(EvalResult.run_id, func.max(EvalResult.created_at))
        .group_by(EvalResult.run_id)
        .order_by(func.max(EvalResult.created_at).desc())
        .first()
    )
    if latest_run:
        run_id = latest_run[0]
        run_rows = db.query(EvalResult).filter(EvalResult.run_id == run_id).all()
        if run_rows:
            eval_pass_rate = round(sum(1 for r in run_rows if r.passed) / len(run_rows), 4)
            for r in run_rows:
                quality_scores.append(QualityScoreItem(grader=r.grader, score=r.score, source="eval_run"))

    return MetricsResponse(
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 6),
        input_tokens=total_input,
        output_tokens=total_output,
        phase_latencies=phase_latencies,
        eval_pass_rate=eval_pass_rate,
        github_sync_success_rate=round(github_sync_success_rate, 4),
        github_sync_fails=failed_count,
        tokens_by_phase=[
            TokenPhaseItem(phase=p, tokens=v["tokens"], cost=round(v["cost"], 6))
            for p, v in phase_token_map.items()
        ],
        latency_by_node=latency_by_node,
        errors_by_phase=[
            ErrorPhaseItem(phase=p, errors=c) for p, c in phase_error_map.items()
        ],
        error_count=len(error_rows),
        daily_token_trend=daily_token_trend,
        retrieval_by_query=retrieval_by_query,
        quality_scores=quality_scores,
        avg_groundedness=avg_groundedness,
    )
