"""Fan-out structured proposal generation.

Generates all 10 canonical sections for a project proposal. Parallel sections
run concurrently via asyncio.gather; sequential chain passes prior output as
extra context to dependent sections.

open_questions is a pure DB read — no LLM call.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.models.project import Project

from app.schemas.proposal_sections import (
    SECTION_SCHEMA_HINTS,
    SECTION_TITLES,
    TYPED_SECTIONS,
    FeatureItem,
    PersonaItem,
    ProposalSectionId,
    RiskItem,
    SectionResponse,
    SectionStatus,
)


@dataclass
class ProposalContext:
    project_name: str
    doc_chunks: str
    clarification_answers: str
    open_tbds: list[str]
    oos_items: list[str]
    tech_stack: dict
    effort_estimates: dict
    chat_history: str


def _get_proposal_llm():
    from langchain_openai import ChatOpenAI

    from app.config import settings

    return ChatOpenAI(
        model=settings.main_llm_model,
        api_key=settings.openai_api_key,
        temperature=settings.temperature,
    )


def _failed_section(section_id: ProposalSectionId, exc: BaseException) -> SectionResponse:
    return SectionResponse(
        section_id=section_id,
        title=SECTION_TITLES[section_id],
        status=SectionStatus.failed,
        generated_at=datetime.utcnow(),
        content=f"Generation failed: {exc}",
        items=None,
    )


def _build_prompt(
    section_id: ProposalSectionId,
    ctx: ProposalContext,
    extra: str = "",
) -> str:
    schema_hint = SECTION_SCHEMA_HINTS[section_id]
    extra_block = f"\n\nAdditional context from prior sections:\n{extra}" if extra else ""

    base = (
        f"You are a senior business analyst writing one section of a formal PRD.\n"
        f"Return ONLY the content for the '{SECTION_TITLES[section_id]}' section.\n"
        f"Format: {schema_hint}\n\n"
        f"Project: {ctx.project_name}\n\n"
        f"Source document excerpts:\n{ctx.doc_chunks or 'Not available.'}\n\n"
        f"Recent chat refinements:\n{ctx.chat_history}\n\n"
        f"Clarification answers:\n{ctx.clarification_answers or 'None.'}"
        f"{extra_block}"
    )

    if section_id == ProposalSectionId.risks_and_mitigations and ctx.oos_items:
        oos_block = "\n".join(f"- {item}" for item in ctx.oos_items)
        base += (
            f"\n\nKnown out-of-scope items (treat as explicit risk signals):\n{oos_block}\n"
            "For each out-of-scope item, create a RiskItem with risk=why it poses a risk "
            "and mitigation=how to handle it. Then add any additional risks identified from "
            "the requirements."
        )

    return base


def _try_parse_items(
    section_id: ProposalSectionId, raw: str
) -> list[dict[str, Any]] | None:
    """Attempt to parse JSON array from LLM response for typed sections."""
    if section_id not in TYPED_SECTIONS:
        return None
    try:
        import re as _re
        text = raw.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        # Extract JSON array even if surrounded by prose
        if not text.startswith("["):
            m = _re.search(r"\[[\s\S]*\]", text)
            if m:
                text = m.group()
        data = json.loads(text)
        if not isinstance(data, list):
            return None
        # Validate with the correct Pydantic model
        model_cls = {
            ProposalSectionId.risks_and_mitigations: RiskItem,
            ProposalSectionId.target_audience: PersonaItem,
            ProposalSectionId.key_features: FeatureItem,
        }[section_id]
        return [model_cls(**item).model_dump() for item in data]
    except Exception:
        return None


async def _gen_section(
    section_id: ProposalSectionId,
    ctx: ProposalContext,
    llm: Any,
    extra: str = "",
) -> SectionResponse:
    prompt = _build_prompt(section_id, ctx, extra)

    is_draft = False
    if section_id == ProposalSectionId.technical_requirements and not ctx.tech_stack:
        is_draft = True
        prompt += "\n\nNote: Phase 3 (tech stack) has not run yet. Generate best-effort content from requirements text."
    if section_id == ProposalSectionId.timeline_and_milestones and not ctx.effort_estimates:
        is_draft = True
        prompt += "\n\nNote: Phase 5 (effort estimation) has not run yet. Generate best-effort content from requirements text."

    try:
        resp = await llm.ainvoke([{"role": "user", "content": prompt}])
        content = resp.content if hasattr(resp, "content") else str(resp)
        items = _try_parse_items(section_id, content)
        status = SectionStatus.draft if is_draft else SectionStatus.generated
        return SectionResponse(
            section_id=section_id,
            title=SECTION_TITLES[section_id],
            status=status,
            generated_at=datetime.utcnow(),
            content=content,
            items=items,
        )
    except Exception as exc:
        return _failed_section(section_id, exc)


async def _fetch_open_questions(ctx: ProposalContext) -> SectionResponse:
    """Zero-LLM section: direct read from context (TBD clarification titles)."""
    items = [{"question": q} for q in ctx.open_tbds]
    content = "\n".join(f"- {q}" for q in ctx.open_tbds) or "No open questions."
    return SectionResponse(
        section_id=ProposalSectionId.open_questions,
        title=SECTION_TITLES[ProposalSectionId.open_questions],
        status=SectionStatus.generated,
        generated_at=datetime.utcnow(),
        content=content,
        items=items if items else None,
    )


async def _build_context(project: Project, db: Session) -> ProposalContext:
    from app.models.clarification import Clarification
    from app.models.enums import TBDStatus
    from app.services.rag import retrieve
    from app.services.workflow import get_workflow

    # RAG chunks
    try:
        chunks, _, _ = await retrieve(
            str(project.id),
            "project requirements scope objectives features",
            top_k=12,
            top_n=12,
        )
        doc_chunks = "\n\n---\n\n".join(c.get("text", "") for c in chunks)
    except Exception:
        doc_chunks = ""

    # Clarifications by status
    all_clars = db.query(Clarification).filter(Clarification.project_id == project.id).all()
    answered = [c for c in all_clars if c.status == TBDStatus.answered and c.answer]
    open_tbds = [c.title for c in all_clars if c.status in (TBDStatus.open, TBDStatus.tbd)]
    oos = [c.answer or c.title for c in all_clars if c.status == TBDStatus.oos]

    clarification_answers = "\n".join(f"- {c.title}: {c.answer}" for c in answered) or "None"

    # Chat history from LangGraph state
    chat_history = "No chat history available."
    try:
        wf = await get_workflow()
        config = {"configurable": {"thread_id": str(project.id)}}
        snapshot = await wf.aget_state(config)
        if snapshot:
            msgs = snapshot.values.get("chat_messages", [])
            if msgs:
                chat_history = "\n".join(
                    f"{m['role'].upper()}: {m['content']}" for m in msgs[-10:]
                )
    except Exception:
        pass

    return ProposalContext(
        project_name=project.name,
        doc_chunks=doc_chunks,
        clarification_answers=clarification_answers,
        open_tbds=open_tbds,
        oos_items=oos,
        tech_stack=project.tech_stack or {},
        effort_estimates=project.effort_estimates or {},
        chat_history=chat_history,
    )


async def generate_structured_proposal(
    project: Project,
    db: Session,
    additional_context: str = "",
) -> list[SectionResponse]:
    """Generate all 10 proposal sections with fan-out concurrency.

    Returns sections in ProposalSectionId enum order. Raises ValueError if
    any section is missing (hard failure — not a warning).
    """
    ctx = await _build_context(project, db)
    if additional_context:
        ctx.chat_history += f"\n\nAdditional PM context: {additional_context}"

    llm = _get_proposal_llm()

    # Step 1: overview first
    overview = await _gen_section(ProposalSectionId.overview, ctx, llm)

    # Step 2: parallel group — run concurrently after overview
    parallel_results = await asyncio.gather(
        _gen_section(ProposalSectionId.target_audience, ctx, llm),
        _gen_section(ProposalSectionId.risks_and_mitigations, ctx, llm),
        _gen_section(ProposalSectionId.success_metrics, ctx, llm),
        _fetch_open_questions(ctx),
        return_exceptions=True,
    )

    # Step 3: sequential chain — each depends on prior section's content
    problem = await _gen_section(ProposalSectionId.problem_statement, ctx, llm)
    goals = await _gen_section(
        ProposalSectionId.goals_and_non_goals, ctx, llm, extra=problem.content
    )
    features = await _gen_section(
        ProposalSectionId.key_features, ctx, llm, extra=goals.content
    )
    tech_req = await _gen_section(
        ProposalSectionId.technical_requirements, ctx, llm, extra=features.content
    )
    timeline = await _gen_section(
        ProposalSectionId.timeline_and_milestones, ctx, llm, extra=features.content
    )

    def _coerce(result: Any, sid: ProposalSectionId) -> SectionResponse:
        if isinstance(result, BaseException):
            return _failed_section(sid, result)
        return result

    sections_map: dict[ProposalSectionId, SectionResponse] = {
        ProposalSectionId.overview: overview,
        ProposalSectionId.problem_statement: problem,
        ProposalSectionId.goals_and_non_goals: goals,
        ProposalSectionId.key_features: features,
        ProposalSectionId.technical_requirements: tech_req,
        ProposalSectionId.timeline_and_milestones: timeline,
        ProposalSectionId.target_audience: _coerce(
            parallel_results[0], ProposalSectionId.target_audience
        ),
        ProposalSectionId.risks_and_mitigations: _coerce(
            parallel_results[1], ProposalSectionId.risks_and_mitigations
        ),
        ProposalSectionId.success_metrics: _coerce(
            parallel_results[2], ProposalSectionId.success_metrics
        ),
        ProposalSectionId.open_questions: _coerce(
            parallel_results[3], ProposalSectionId.open_questions
        ),
    }

    # Enforce all 10 sections present — hard failure, not a warning
    missing = [sid for sid in ProposalSectionId if sid not in sections_map]
    if missing:
        raise ValueError(f"Missing sections: {missing}")

    return [sections_map[sid] for sid in ProposalSectionId]


async def generate_structured_proposal_stream(
    project: Project,
    db: Session,
    additional_context: str = "",
):
    """Async generator: yields each SectionResponse as it completes.

    Emission order: overview → parallel group (4) → sequential chain (5).
    """
    ctx = await _build_context(project, db)
    if additional_context:
        ctx.chat_history += f"\n\nAdditional PM context: {additional_context}"

    llm = _get_proposal_llm()

    overview = await _gen_section(ProposalSectionId.overview, ctx, llm)
    yield overview

    parallel_results = await asyncio.gather(
        _gen_section(ProposalSectionId.target_audience, ctx, llm),
        _gen_section(ProposalSectionId.risks_and_mitigations, ctx, llm),
        _gen_section(ProposalSectionId.success_metrics, ctx, llm),
        _fetch_open_questions(ctx),
        return_exceptions=True,
    )
    parallel_ids = [
        ProposalSectionId.target_audience,
        ProposalSectionId.risks_and_mitigations,
        ProposalSectionId.success_metrics,
        ProposalSectionId.open_questions,
    ]
    for result, sid in zip(parallel_results, parallel_ids):
        yield result if isinstance(result, SectionResponse) else _failed_section(sid, result)

    problem = await _gen_section(ProposalSectionId.problem_statement, ctx, llm)
    yield problem

    goals = await _gen_section(ProposalSectionId.goals_and_non_goals, ctx, llm, extra=problem.content)
    yield goals

    features = await _gen_section(ProposalSectionId.key_features, ctx, llm, extra=goals.content)
    yield features

    tech_req = await _gen_section(ProposalSectionId.technical_requirements, ctx, llm, extra=features.content)
    yield tech_req

    timeline = await _gen_section(ProposalSectionId.timeline_and_milestones, ctx, llm, extra=features.content)
    yield timeline


async def generate_single_section(
    section_id: ProposalSectionId,
    project: Project,
    db: Session,
    additional_context: str = "",
) -> SectionResponse:
    """Regenerate a single section in isolation."""
    ctx = await _build_context(project, db)
    if additional_context:
        ctx.chat_history += f"\n\nAdditional PM context: {additional_context}"
    llm = _get_proposal_llm()
    return await _gen_section(section_id, ctx, llm)
