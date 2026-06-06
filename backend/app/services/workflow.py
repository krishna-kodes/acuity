"""LangGraph workflow — ProjectState, phase nodes, SqliteSaver checkpointer.

Phases 1–3 are deterministic pipeline nodes (stubs; real logic wired in E5-T6).
Phases 4–6 are LangGraph ReAct agents.

Usage:
    result = await run_phase(project_id="42", state_update={"phase_status": {"phase_1": "complete"}})
"""

import asyncio
import sqlite3
from functools import wraps
from typing import Any, TypedDict

from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent


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
}


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

@with_retry()
async def _phase_2_chat_node(state: ProjectState) -> dict[str, Any]:
    """Phase 2: Chat & refinement — detect TBDs, surface clarifications.

    Stub: marks phase in_progress. Real RAG pipeline wired in E5-T6.
    """
    _require_phase_complete(state, 2)
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "in_progress"
    return {"phase_status": ps}


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

    workflow.add_node("phase_2_chat", _phase_2_chat_node)
    workflow.add_node("phase_3_stack", _phase_3_stack_node)
    workflow.add_node("phase_4_team", _phase_4_team_node)
    workflow.add_node("phase_5_estimate", _phase_5_estimate_node)
    workflow.add_node("phase_6_epics", _phase_6_epics_node)

    workflow.set_entry_point("phase_2_chat")
    workflow.add_edge("phase_2_chat", "phase_3_stack")
    workflow.add_edge("phase_3_stack", "phase_4_team")
    workflow.add_edge("phase_4_team", "phase_5_estimate")
    workflow.add_edge("phase_5_estimate", "phase_6_epics")
    workflow.add_edge("phase_6_epics", END)

    return workflow.compile(
        checkpointer=checkpointer,
        # Pause after each phase so the PM can review before proceeding
        interrupt_after=[
            "phase_2_chat",
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
