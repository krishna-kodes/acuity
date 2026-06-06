"""LangGraph workflow — ProjectState, phase nodes, SqliteSaver checkpointer.

Phases 1–3 are deterministic pipeline nodes (stubs; real logic wired in E5-T6).
Phases 4–6 are LangGraph ReAct agents.

Usage:
    result = await run_phase(
        project_id="42", state_update={"phase_status": {"phase_1": "complete"}}
    )
"""

import asyncio
import sqlite3
from functools import wraps
from typing import Any, TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

# Module-level imports so tests can patch app.services.workflow.<name>
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
    """Return employees matching the requested skills from the employees table."""
    # TODO(E5-T6): query employees + employee_skills tables
    return []


@tool
def get_historical_projects() -> list[dict]:
    """Return historical projects for effort calibration."""
    # TODO(E5-T6): query historical_projects table
    return []


@tool
def estimate_effort(proposal_summary: str, team_size: int, reference_projects: list[dict]) -> dict:
    """Estimate effort in weeks and story points given team and historical data."""
    # TODO(E5-T6): real LLM-based estimation
    return {"total_weeks": 8, "total_points": 32, "confidence": 0.7}


@tool
def generate_epics_tool(proposal_summary: str, tech_stack_summary: str) -> list[dict]:
    """Generate a list of epics (GitHub milestones) and tasks from the proposal."""
    # TODO(E5-T6): real structured output generation
    return []


_PHASE_4_TOOLS = [get_employees]
_PHASE_5_TOOLS = [get_historical_projects, estimate_effort]
_PHASE_6_TOOLS = [generate_epics_tool]


# ---------------------------------------------------------------------------
# Phase nodes
# ---------------------------------------------------------------------------

async def _phase_2_init_node(state: ProjectState) -> dict[str, Any]:
    """Phase 2: initialise chat loop."""
    # Only guard if phase_status already exists (not a fresh thread seeded by endpoint)
    if state.get("phase_status"):
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
    async for chunk in llm.astream(lc_messages):
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


def _chat_routing(state: ProjectState) -> str:
    """Pure routing function — returns next node name, never mutates state."""
    return "phase_2_complete" if state.get("chat_proceed") else "chat_turn"


@with_retry()
async def _phase_3_stack_node(state: ProjectState) -> dict[str, Any]:
    """Phase 3: Tech stack suggestion.

    Stub: returns placeholder stack. Real LLM call wired in E5-T6.
    """
    _require_phase_complete(state, 3)
    ps = dict(state.get("phase_status") or {})
    ps["phase_3"] = "in_progress"
    return {
        "phase_status": ps,
        "tech_stack": {
            "frontend": ["Next.js"],
            "backend": ["FastAPI"],
            "database": ["SQLite"],
            "infra": ["Railway"],
            "rationale": "Stub — populated by LangGraph in E5-T6.",
        },
    }


async def _phase_4_team_node(state: ProjectState) -> dict[str, Any]:
    """Phase 4: Team suggestion — ReAct agent queries employee skills.

    Builds a fresh agent per invocation so the LLM is resolved at runtime.
    """
    _require_phase_complete(state, 4)
    from app.services.llm_factory import get_llm

    agent = create_react_agent(get_llm(), _PHASE_4_TOOLS)
    agent_result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Suggest a team for project {state.get('project_id')}. "
                        "Use the get_employees tool to find suitable engineers."
                    ),
                }
            ]
        }
    )
    ps = dict(state.get("phase_status") or {})
    ps["phase_4"] = "complete"
    return {
        "phase_status": ps,
        "team_suggestion": {
            "members": [],
            "agent_messages": len(agent_result.get("messages", [])),
        },
    }


async def _phase_5_estimate_node(state: ProjectState) -> dict[str, Any]:
    """Phase 5: Effort estimation — ReAct agent pulls historical data."""
    _require_phase_complete(state, 5)
    from app.services.llm_factory import get_llm

    agent = create_react_agent(get_llm(), _PHASE_5_TOOLS)
    agent_result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Estimate effort for project {state.get('project_id')}. "
                        "Use get_historical_projects and estimate_effort tools."
                    ),
                }
            ]
        }
    )
    ps = dict(state.get("phase_status") or {})
    ps["phase_5"] = "complete"
    return {
        "phase_status": ps,
        "effort_estimates": {
            "total_weeks": 8,
            "total_points": 32,
            "agent_messages": len(agent_result.get("messages", [])),
        },
    }


async def _phase_6_epics_node(state: ProjectState) -> dict[str, Any]:
    """Phase 6: Epic & task generation — ReAct agent, then GitHub sync."""
    _require_phase_complete(state, 6)
    from app.services.llm_factory import get_llm

    agent = create_react_agent(get_llm(), _PHASE_6_TOOLS)
    agent_result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Generate epics and tasks for project {state.get('project_id')}. "
                        "Use generate_epics_tool."
                    ),
                }
            ]
        }
    )
    ps = dict(state.get("phase_status") or {})
    ps["phase_6"] = "complete"
    return {
        "phase_status": ps,
        "epics": agent_result.get("epics", []),
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

_workflow_instance = None
_sqlite_conn = None


def build_workflow():
    """Build and compile the LangGraph StateGraph with SqliteSaver checkpointer.

    Returns a CompiledStateGraph pausing after each phase (interrupt_after).
    Callers invoke the graph per PM "Proceed" action; the checkpointer
    resumes from the last completed phase using thread_id = project_id.
    """
    global _sqlite_conn
    # Keep connection open for the lifetime of the module (ADR-002: SqliteSaver)
    _sqlite_conn = sqlite3.connect("./project_state.db", check_same_thread=False)
    checkpointer = SqliteSaver(_sqlite_conn)

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
        # Pause after each phase so the PM can review before proceeding
        interrupt_after=[
            "chat_turn",
            "phase_3_stack",
            "phase_4_team",
            "phase_5_estimate",
        ],
    )


def get_workflow():
    """Return the module-level compiled workflow (lazy singleton)."""
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = build_workflow()
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
    wf = get_workflow()
    config: dict = {"configurable": {"thread_id": project_id}}

    existing = wf.get_state(config)

    if existing.values:
        if state_update:
            wf.update_state(config, state_update)
        result = await wf.ainvoke(None, config=config)
    else:
        initial: ProjectState = {**_EMPTY_STATE, "project_id": project_id}
        if state_update:
            initial.update(state_update)  # type: ignore[typeddict-item]
        result = await wf.ainvoke(initial, config=config)

    return result or {}
