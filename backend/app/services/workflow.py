"""LangGraph workflow — ProjectState, phase nodes, SqliteSaver checkpointer.

Phases 1–3 are deterministic pipeline nodes (stubs; real logic wired in E5-T6).
Phases 4–6 are LangGraph ReAct agents.

Usage:
    result = await run_phase(
        project_id="42", state_update={"phase_status": {"phase_1": "complete"}}
    )
"""

import asyncio
from functools import wraps
from typing import Any, TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

import json as _json

# Module-level imports so tests can patch app.services.workflow.<name>
from app.database import SessionLocal
from app.models.employee import Employee, EmployeeSkill, Skill
from app.models.reference import ApprovedTechnology, HistoricalProject
from app.services.llm_factory import get_llm
from app.services.rag import retrieve
from app.services.tbd_detection import detect_tbds

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class ProjectState(TypedDict):
    project_id: str
    raw_doc_text: str
    proposal_state: dict
    tbd_items: list
    tech_stack: dict
    team_suggestion: dict
    effort_estimates: dict
    epics: list
    metrics: dict
    phase_status: dict  # {"phase_1": "complete", "phase_2": "in_progress", ...}
    chat_messages: list          # NEW: list of {"role": str, "content": str}
    chat_proceed: bool           # NEW: set True by PM to exit chat loop
    groundedness_score: float | None  # NEW: last groundedness check score


_EMPTY_STATE: ProjectState = {
    "project_id": "",
    "raw_doc_text": "",
    "proposal_state": {},
    "tbd_items": [],
    "tech_stack": {},
    "team_suggestion": {},
    "effort_estimates": {},
    "epics": [],
    "metrics": {},
    "phase_status": {},
    "chat_messages": [],
    "chat_proceed": False,
    "groundedness_score": None,
}


class _GroundednessResult(BaseModel):
    score: float
    reasoning: str
    unsupported_claims: list[str]


_GROUNDEDNESS_PROMPT = (
    "System: You are an evaluation judge. Answer only with a JSON object.\n"
    "User:\n"
    "  Context: {context}\n"
    "  Response: {response}\n"
    "  Question: Is every factual claim in the Response directly supported by the Context?\n"
    "  Score 0-1 where 1 = fully grounded, 0 = contains unsupported claims.\n"
    '  Output: {{"score": float, "reasoning": str, "unsupported_claims": list[str]}}'
)


# ---------------------------------------------------------------------------
# Phase guard
# ---------------------------------------------------------------------------

def _require_phase_complete(state: ProjectState, phase_num: int) -> None:
    """Raise ValueError if the preceding phase is not complete.

    Callers convert this to HTTP 409 at the router level.
    """
    if phase_num <= 1:
        return
    key = f"phase_{phase_num - 1}"
    status = state.get("phase_status") or {}
    if status.get(key) != "complete":
        raise ValueError(
            f"Phase {phase_num - 1} must be complete before starting phase {phase_num}. "
            f"Current status: {status.get(key)!r}"
        )


# ---------------------------------------------------------------------------
# Retry decorator (node-level, per ADR-005)
# ---------------------------------------------------------------------------

def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Exponential-backoff retry for async node functions."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await fn(*args, **kwargs)
                except Exception:
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(base_delay * (2 ** attempt))
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Phase 4–6 tools (stub implementations; real DB queries wired in E5-T6)
# ---------------------------------------------------------------------------

@tool
def get_employees(skills: list[str]) -> list[dict]:
    """Query employees who have any of the requested skills."""
    db = SessionLocal()
    try:
        employees = (
            db.query(Employee)
            .join(EmployeeSkill, Employee.id == EmployeeSkill.employee_id)
            .join(Skill, EmployeeSkill.skill_id == Skill.id)
            .filter(Skill.name.in_(skills))
            .distinct()
            .all()
        )
        return [
            {
                "id": emp.id,
                "name": emp.name,
                "seniority": emp.seniority,
                "availability_pct": emp.availability_pct,
                "skills": [es.skill.name for es in emp.employee_skills],
            }
            for emp in employees
        ]
    finally:
        db.close()


@tool
def get_historical_projects() -> list[dict]:
    """Retrieve historical projects for effort calibration."""
    db = SessionLocal()
    try:
        projects = db.query(HistoricalProject).limit(10).all()
        return [
            {
                "name": p.name,
                "domain": p.domain or "",
                "estimated_points": p.estimated_points or 0,
                "actual_points": p.actual_points or 0,
                "duration_weeks": p.duration_weeks or 0,
                "team_size": p.team_size or 0,
            }
            for p in projects
        ]
    finally:
        db.close()


@tool
def estimate_effort(proposal_summary: str, team_size: int, reference_projects: list[dict]) -> dict:
    """Estimate effort in weeks and story points given team and historical data."""
    from app.schemas.project import EpicsOutput

    class _EffortEstimate(BaseModel):
        total_weeks: int
        total_points: int
        confidence: float
        breakdown: dict[str, int]
        reasoning: str

    llm = get_llm(fast=True).with_structured_output(_EffortEstimate)
    refs = "\n".join(
        f"- {p['name']}: {p['duration_weeks']}w, {p['team_size']} devs, {p['estimated_points']} pts"
        for p in reference_projects[:5]
    ) or "No reference projects available."

    result = llm.invoke(
        f"Estimate effort for this project:\n{proposal_summary}\n\n"
        f"Team size: {team_size}\n\n"
        f"Reference projects:\n{refs}\n\n"
        "Return total_weeks (int), total_points (int), confidence (0.0-1.0), "
        "breakdown as dict of phase_name->points, and reasoning."
    )
    return result.model_dump()


_EPIC_GENERATION_PROMPT = (
    "You are a technical project manager. Generate a realistic set of epics and tasks "
    "for the following project.\n\n"
    "Project proposal:\n{proposal_summary}\n\n"
    "Tech stack: {tech_stack_summary}\n\n"
    "Today's date: {today}\n\n"
    "Rules:\n"
    "- Generate 3–6 epics\n"
    "- Each epic has 2–4 tasks\n"
    "- story_points must be one of: 1, 2, 3, 5, 8, 13\n"
    "- due_date in YYYY-MM-DD format, starting 4 weeks from today\n"
    "- labels from: frontend, backend, database, infra, testing, docs"
)


@tool
def generate_epics_tool(proposal_summary: str, tech_stack_summary: str) -> list[dict]:
    """Generate a list of epics and tasks using structured LLM output."""
    from datetime import date
    from app.schemas.project import EpicsOutput

    llm = get_llm(fast=False).with_structured_output(EpicsOutput)
    today = date.today().isoformat()

    result = llm.invoke(
        _EPIC_GENERATION_PROMPT.format(
            proposal_summary=proposal_summary,
            tech_stack_summary=tech_stack_summary,
            today=today,
        )
    )
    return [e.model_dump() for e in result.epics]


_PHASE_4_TOOLS = [get_employees]
_PHASE_5_TOOLS = [get_historical_projects, estimate_effort]
_PHASE_6_TOOLS = [generate_epics_tool]


# ---------------------------------------------------------------------------
# Phase nodes
# ---------------------------------------------------------------------------

async def _phase_2_init_node(state: ProjectState) -> dict[str, Any]:
    """Phase 2: initialise chat loop."""
    # Guard unless phase_status is None (completely absent — LangGraph fresh thread)
    if state.get("phase_status") is not None:
        _require_phase_complete(state, 2)
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "in_progress"
    # Only reset chat_messages if this is a fresh Phase 2 start (no existing messages)
    existing_messages = state.get("chat_messages") or []
    return {
        "phase_status": ps,
        "chat_messages": existing_messages if existing_messages else [],
        "chat_proceed": False,
    }


@with_retry()
async def _chat_turn_node(state: ProjectState) -> dict[str, Any]:
    """One RAG chat turn: retrieve -> detect TBDs -> LLM response -> groundedness check."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    from app.config import settings

    messages = list(state.get("chat_messages") or [])
    project_id = state["project_id"]
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    chunks = await retrieve(project_id, last_user)
    context = "\n\n".join(
        f"[{c.get('section_hint', '')}] {c['text']}" for c in chunks
    )

    known = {t.get("text", "") for t in (state.get("tbd_items") or [])}
    new_tbds = await detect_tbds(last_user, chunks, known_tbds=known)

    lc_messages = [
        SystemMessage(content=f"Answer using only this context:\n\n{context}"),
        *[
            HumanMessage(content=m["content"]) if m["role"] == "user"
            else AIMessage(content=m["content"])
            for m in messages
        ],
    ]
    llm = get_llm()
    response_parts: list[str] = []
    async for chunk in llm.with_config({"run_name": "chat_response"}).astream(lc_messages):
        if isinstance(chunk.content, str):
            response_parts.append(chunk.content)
    response_content = "".join(response_parts)

    groundedness_score = None
    if settings.groundedness_check_enabled:
        judge = llm.with_structured_output(_GroundednessResult)
        gs = await judge.with_config({"run_name": "groundedness_judge"}).ainvoke([
            HumanMessage(content=_GROUNDEDNESS_PROMPT.format(
                context=context, response=response_content
            ))
        ])
        groundedness_score = float(gs.score) if hasattr(gs, "score") else None

    messages.append({"role": "assistant", "content": response_content})
    return {
        "chat_messages": messages,
        "tbd_items": list(state.get("tbd_items") or []) + new_tbds,
        "groundedness_score": groundedness_score,
    }


async def _phase_2_complete_node(state: ProjectState) -> dict[str, Any]:
    """Marks Phase 2 complete when PM clicks Proceed."""
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "complete"
    return {"phase_status": ps}


# Alias used by tests written against earlier node naming
_phase_2_chat_node = _phase_2_init_node


def _chat_routing(state: ProjectState) -> str:
    """Pure routing function — returns next node name, never mutates state."""
    return "phase_2_complete" if state.get("chat_proceed") else "chat_turn"


@with_retry()
async def _phase_3_stack_node(state: ProjectState) -> dict[str, Any]:
    """Phase 3: Tech stack suggestion — queries approved_technologies DB + LLM."""
    _require_phase_complete(state, 3)

    ps = dict(state.get("phase_status") or {})
    ps["phase_3"] = "in_progress"

    db = SessionLocal()
    try:
        techs = db.query(ApprovedTechnology).all()
        tech_list = [
            {"name": t.name, "category": t.category, "tags": t.tags or ""}
            for t in techs
        ]
    finally:
        db.close()

    class _TechStackChoice(BaseModel):
        frontend: list[str]
        backend: list[str]
        database: list[str]
        infra: list[str]
        rationale: str

    proposal_summary = state.get("proposal_state", {}).get("summary", "No proposal summary available.")
    tech_descriptions = "\n".join(
        f"- {t['name']} ({t['category']}): {t['tags']}" for t in tech_list
    ) or "No approved technologies in database."

    _FALLBACK_STACK = {
        "frontend": ["Next.js"],
        "backend": ["FastAPI"],
        "database": ["SQLite"],
        "infra": ["Railway"],
        "rationale": "Default stack — LLM unavailable.",
    }

    try:
        llm = get_llm(fast=False).with_structured_output(_TechStackChoice)
        result = llm.invoke(
            f"Given this project proposal:\n{proposal_summary}\n\n"
            f"Select the most appropriate technologies from this approved list:\n{tech_descriptions}\n\n"
            "Choose 1-3 per category. Return frontend, backend, database, infra lists and a brief rationale."
        )
        tech_stack = result.model_dump()
        ps["phase_3"] = "complete"
    except Exception:
        tech_stack = _FALLBACK_STACK

    return {"phase_status": ps, "tech_stack": tech_stack}


async def _phase_4_team_node(state: ProjectState) -> dict[str, Any]:
    """Phase 4: Team suggestion — ReAct agent queries employee skills."""
    _require_phase_complete(state, 4)

    tech_stack = state.get("tech_stack") or {}
    all_technologies = (
        tech_stack.get("frontend", []) + tech_stack.get("backend", []) +
        tech_stack.get("database", []) + tech_stack.get("infra", [])
    )

    agent = create_react_agent(get_llm(), _PHASE_4_TOOLS)
    agent_result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Find employees for a project using these technologies: {all_technologies}. "
                        "Use the get_employees tool to query the database. "
                        "Return the list of suitable team members."
                    ),
                }
            ]
        }
    )

    # Extract employee data from tool call results
    members = []
    for msg in agent_result.get("messages", []):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            try:
                parsed = _json.loads(msg.content)
                if isinstance(parsed, list) and parsed and "name" in parsed[0]:
                    members = parsed
                    break
            except (_json.JSONDecodeError, (KeyError, IndexError)):
                pass

    ps = dict(state.get("phase_status") or {})
    ps["phase_4"] = "complete"
    return {
        "phase_status": ps,
        "team_suggestion": {"members": members, "technologies": all_technologies},
    }


async def _phase_5_estimate_node(state: ProjectState) -> dict[str, Any]:
    """Phase 5: Effort estimation — ReAct agent pulls historical data."""
    _require_phase_complete(state, 5)

    proposal_summary = state.get("proposal_state", {}).get("summary", "No proposal available.")
    team_size = len(state.get("team_suggestion", {}).get("members", [])) or 3

    agent = create_react_agent(get_llm(), _PHASE_5_TOOLS)
    agent_result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Estimate effort for this project:\n{proposal_summary}\n\n"
                        f"Team size: {team_size}\n\n"
                        "1. Use get_historical_projects to get reference data.\n"
                        "2. Use estimate_effort with the proposal summary, team size, and reference projects.\n"
                        "Return the full estimation result."
                    ),
                }
            ]
        }
    )

    # Extract effort data from tool call results
    effort: dict = {"total_weeks": 8, "total_points": 32, "confidence": 0.7}
    for msg in agent_result.get("messages", []):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            try:
                parsed = _json.loads(msg.content)
                if isinstance(parsed, dict) and "total_weeks" in parsed:
                    effort = parsed
                    break
            except _json.JSONDecodeError:
                pass

    ps = dict(state.get("phase_status") or {})
    ps["phase_5"] = "complete"
    return {"phase_status": ps, "effort_estimates": effort}


async def _phase_6_epics_node(state: ProjectState) -> dict[str, Any]:
    """Phase 6: Epic & task generation — ReAct agent with structured LLM output."""
    _require_phase_complete(state, 6)

    proposal_summary = state.get("proposal_state", {}).get("summary", "No proposal available.")
    tech_stack = state.get("tech_stack") or {}
    tech_stack_summary = ", ".join(
        tech_stack.get("frontend", []) + tech_stack.get("backend", []) +
        tech_stack.get("database", []) + tech_stack.get("infra", [])
    ) or "Standard web stack"

    agent = create_react_agent(get_llm(), _PHASE_6_TOOLS)
    agent_result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Generate epics and tasks for this project.\n\n"
                        f"Proposal: {proposal_summary}\n\n"
                        f"Tech stack: {tech_stack_summary}\n\n"
                        "Use generate_epics_tool with the proposal and tech stack summaries."
                    ),
                }
            ]
        }
    )

    # Extract epics from tool call results
    epics: list = []
    for msg in agent_result.get("messages", []):
        if hasattr(msg, "content") and isinstance(msg.content, str):
            try:
                parsed = _json.loads(msg.content)
                if isinstance(parsed, list) and parsed and "title" in parsed[0]:
                    epics = parsed
                    break
            except _json.JSONDecodeError:
                pass

    ps = dict(state.get("phase_status") or {})
    ps["phase_6"] = "complete"
    return {"phase_status": ps, "epics": epics}


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

_workflow_instance = None
_aiosqlite_conn = None


def _compile_graph(checkpointer) -> "CompiledStateGraph":
    workflow = StateGraph(ProjectState)

    workflow.add_node("phase_2_init",     _phase_2_init_node)
    workflow.add_node("chat_turn",        _chat_turn_node)
    workflow.add_node("phase_2_complete", _phase_2_complete_node)
    workflow.add_node("phase_3_stack",    _phase_3_stack_node)
    workflow.add_node("phase_4_team",     _phase_4_team_node)
    workflow.add_node("phase_5_estimate", _phase_5_estimate_node)
    workflow.add_node("phase_6_epics",    _phase_6_epics_node)

    workflow.set_entry_point("phase_2_init")
    workflow.add_edge("phase_2_init",     "chat_turn")
    workflow.add_conditional_edges("chat_turn", _chat_routing)
    workflow.add_edge("phase_2_complete", "phase_3_stack")
    workflow.add_edge("phase_3_stack",    "phase_4_team")
    workflow.add_edge("phase_4_team",     "phase_5_estimate")
    workflow.add_edge("phase_5_estimate", "phase_6_epics")
    workflow.add_edge("phase_6_epics",    END)

    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=[
            "chat_turn",
            "phase_3_stack",
            "phase_4_team",
            "phase_5_estimate",
        ],
    )


async def get_workflow():
    """Return the module-level compiled workflow (lazy async singleton)."""
    global _workflow_instance, _aiosqlite_conn
    if _workflow_instance is None:
        import aiosqlite
        _aiosqlite_conn = await aiosqlite.connect("./project_state.db")
        checkpointer = AsyncSqliteSaver(_aiosqlite_conn)
        _workflow_instance = _compile_graph(checkpointer)
    return _workflow_instance


async def run_phase(project_id: str, state_update: dict | None = None) -> dict:
    """Advance the workflow one phase for the given project.

    On first call: initialises state and runs phase 2 (phase 1 is the ingestion
    pipeline, not a LangGraph node). On subsequent calls: resumes from the last
    interrupt point, optionally merging caller-provided state_update first.

    Args:
        project_id: Used as LangGraph thread_id for checkpoint isolation.
        state_update: Optional state fields to merge before resuming.

    Returns:
        The updated ProjectState dict after the phase completes.
    """
    wf = await get_workflow()
    config: dict = {"configurable": {"thread_id": project_id}}

    existing = await wf.aget_state(config)

    if existing.values:
        if state_update:
            await wf.aupdate_state(config, state_update)
        result = await wf.ainvoke(None, config=config)
    else:
        initial: ProjectState = {**_EMPTY_STATE, "project_id": project_id}
        if state_update:
            initial.update(state_update)  # type: ignore[typeddict-item]
        result = await wf.ainvoke(initial, config=config)

    return result or {}
