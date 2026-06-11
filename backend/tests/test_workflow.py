"""Tests for E5-T3: LangGraph workflow, ProjectState, phase guard, retry, LLM factory."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.services.workflow import (
    _EMPTY_STATE,
    ProjectState,
    _phase_2_chat_node,
    _phase_3_stack_node,
    _require_phase_complete,
    with_retry,
)

# ---------------------------------------------------------------------------
# ProjectState shape
# ---------------------------------------------------------------------------

def test_project_state_has_required_keys():
    keys = set(ProjectState.__annotations__.keys())
    required = {
        "project_id", "raw_doc_text", "proposal_state", "tbd_items",
        "tech_stack", "team_suggestion", "effort_estimates", "epics",
        "metrics", "phase_status",
    }
    assert required.issubset(keys)


def test_empty_state_has_all_keys():
    for key in ProjectState.__annotations__:
        assert key in _EMPTY_STATE


# ---------------------------------------------------------------------------
# Phase guard
# ---------------------------------------------------------------------------

def test_phase_guard_allows_phase_1():
    _require_phase_complete({"phase_status": {}}, 1)  # no exception


def test_phase_guard_allows_phase_2_when_phase_1_complete():
    state: ProjectState = {**_EMPTY_STATE, "phase_status": {"phase_1": "complete"}}
    _require_phase_complete(state, 2)  # no exception


def test_phase_guard_blocks_phase_2_when_phase_1_not_complete():
    state: ProjectState = {**_EMPTY_STATE, "phase_status": {"phase_1": "in_progress"}}
    with pytest.raises(ValueError, match="Phase 1 must be complete"):
        _require_phase_complete(state, 2)


def test_phase_guard_blocks_phase_3_when_phase_2_incomplete():
    state: ProjectState = {**_EMPTY_STATE, "phase_status": {"phase_1": "complete"}}
    with pytest.raises(ValueError, match="Phase 2 must be complete"):
        _require_phase_complete(state, 3)


def test_phase_guard_allows_phase_3_when_phase_2_complete():
    state: ProjectState = {
        **_EMPTY_STATE,
        "phase_status": {"phase_1": "complete", "phase_2": "complete"},
    }
    _require_phase_complete(state, 3)  # no exception


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def test_retry_succeeds_first_attempt():
    call_count = 0

    async def node(state):
        nonlocal call_count
        call_count += 1
        return {"result": "ok"}

    decorated = with_retry(max_retries=3, base_delay=0.0)(node)
    result = asyncio.run(decorated({}))
    assert result == {"result": "ok"}
    assert call_count == 1


def test_retry_retries_on_exception_then_succeeds():
    call_count = 0

    async def node(state):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("transient")
        return {"result": "ok"}

    decorated = with_retry(max_retries=3, base_delay=0.0)(node)
    result = asyncio.run(decorated({}))
    assert call_count == 3
    assert result == {"result": "ok"}


def test_retry_raises_after_max_attempts():
    async def node(state):
        raise RuntimeError("always fails")

    decorated = with_retry(max_retries=3, base_delay=0.0)(node)
    with pytest.raises(RuntimeError, match="always fails"):
        asyncio.run(decorated({}))


# ---------------------------------------------------------------------------
# Phase 2 node (stub)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_2_chat_node_marks_in_progress():
    state: ProjectState = {**_EMPTY_STATE, "phase_status": {"phase_1": "complete"}}
    result = await _phase_2_chat_node(state)
    assert result["phase_status"]["phase_2"] == "in_progress"


@pytest.mark.asyncio
async def test_phase_2_chat_node_raises_409_when_phase_1_incomplete():
    state: ProjectState = {**_EMPTY_STATE, "phase_status": {}}
    with pytest.raises(ValueError, match="Phase 1 must be complete"):
        await _phase_2_chat_node(state)


# ---------------------------------------------------------------------------
# Phase 3 node (stub)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase_3_stack_node_returns_tech_stack():

    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    state: ProjectState = {
        **_EMPTY_STATE,
        "project_id": "1",
        "phase_status": {"phase_1": "complete", "phase_2": "complete"},
    }
    with patch("app.services.workflow.record_error"), \
         patch("app.services.workflow.SessionLocal", return_value=mock_db):
        result = await _phase_3_stack_node(state)
    assert "tech_stack" in result
    assert "frontend" in result["tech_stack"]
    assert result["phase_status"]["phase_3"] == "complete"


@pytest.mark.asyncio
async def test_phase_3_stack_node_raises_when_phase_2_incomplete():
    state: ProjectState = {**_EMPTY_STATE, "phase_status": {"phase_1": "complete"}}
    with pytest.raises(ValueError, match="Phase 2 must be complete"):
        await _phase_3_stack_node(state)


@pytest.mark.asyncio
async def test_phase_3_stack_node_logs_error_on_llm_failure():
    from unittest.mock import patch

    state: ProjectState = {
        **_EMPTY_STATE,
        "project_id": "42",
        "phase_status": {"phase_1": "complete", "phase_2": "complete"},
    }

    mock_db = MagicMock()
    mock_db.query.return_value.all.return_value = []
    mock_db.__enter__ = MagicMock(return_value=mock_db)
    mock_db.__exit__ = MagicMock(return_value=False)

    with patch("app.services.workflow.record_error") as mock_record_error, \
         patch("app.services.workflow.get_llm") as mock_llm, \
         patch("app.services.workflow.SessionLocal", return_value=mock_db):
        mock_llm.return_value.with_structured_output.side_effect = RuntimeError("API key invalid")
        result = await _phase_3_stack_node(state)

    # Fallback stack returned and phase marked complete
    assert result["tech_stack"]["frontend"] == ["Next.js"]
    assert result["phase_status"]["phase_3"] == "complete"

    # record_error called with correct phase and error type
    mock_record_error.assert_called_once()
    call_args = mock_record_error.call_args[0]
    assert call_args[1] == "phase_3"
    assert call_args[2] == "RuntimeError"


# ---------------------------------------------------------------------------
# LLM factory
# ---------------------------------------------------------------------------

def test_llm_factory_google():
    from unittest.mock import patch

    from app.services.llm_factory import get_llm

    with patch("app.config.settings") as mock_settings:
        mock_settings.main_llm_provider = "google"
        mock_settings.main_llm_model = "gemini-2.5-flash"
        mock_settings.temperature = 0.0
        mock_settings.google_api_key = "test-key"

        with patch("app.services.llm_factory.settings", mock_settings):
            llm = get_llm(fast=False)

    from langchain_google_genai import ChatGoogleGenerativeAI
    assert isinstance(llm, ChatGoogleGenerativeAI)


def test_llm_factory_anthropic():
    from unittest.mock import patch

    from app.services.llm_factory import get_llm

    with patch("app.config.settings") as mock_settings:
        mock_settings.fast_llm_provider = "anthropic"
        mock_settings.fast_llm_model = "claude-haiku-4-5-20251001"
        mock_settings.temperature = 0.0
        mock_settings.anthropic_api_key = "test-key"

        with patch("app.services.llm_factory.settings", mock_settings):
            llm = get_llm(fast=True)

    from langchain_anthropic import ChatAnthropic
    assert isinstance(llm, ChatAnthropic)


def test_llm_factory_unknown_provider_raises():
    from unittest.mock import patch

    from app.services.llm_factory import get_llm

    with patch("app.config.settings") as mock_settings:
        mock_settings.main_llm_provider = "cohere"
        mock_settings.main_llm_model = "command"
        mock_settings.temperature = 0.0
        mock_settings.google_api_key = ""

        with patch("app.services.llm_factory.settings", mock_settings):
            with pytest.raises(ValueError, match="Unknown LLM provider"):
                get_llm()


# ---------------------------------------------------------------------------
# build_workflow smoke test
# ---------------------------------------------------------------------------

def test_build_workflow_returns_compiled_graph():
    import sqlite3 as _sqlite3

    from langgraph.graph.state import CompiledStateGraph

    import app.services.workflow as wf_module

    # build_workflow() doesn't call get_llm — LLM is lazy-loaded inside node functions.
    # Patch sqlite3.connect to return an in-memory DB so no file is created.
    real_conn = _sqlite3.connect(":memory:", check_same_thread=False)
    with patch("app.services.workflow.sqlite3.connect", return_value=real_conn):
        original_instance = wf_module._workflow_instance
        wf_module._workflow_instance = None
        try:
            graph = wf_module.build_workflow()
            assert isinstance(graph, CompiledStateGraph)
        finally:
            wf_module._workflow_instance = original_instance
            real_conn.close()
