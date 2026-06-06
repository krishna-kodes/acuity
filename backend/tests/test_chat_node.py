from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_chat_routing_loops_without_proceed():
    from app.services.workflow import _chat_routing
    result = _chat_routing({"chat_proceed": False, "project_id": "1"})
    assert result == "chat_turn"


def test_chat_routing_loops_when_proceed_missing():
    from app.services.workflow import _chat_routing
    result = _chat_routing({"project_id": "1"})
    assert result == "chat_turn"


def test_chat_routing_advances_with_proceed():
    from app.services.workflow import _chat_routing
    result = _chat_routing({"chat_proceed": True, "project_id": "1"})
    assert result == "phase_2_complete"


@pytest.mark.asyncio
async def test_phase_2_init_sets_status():
    from app.services.workflow import _phase_2_init_node
    state = {
        "project_id": "1",
        "phase_status": {"phase_1": "complete"},
        "chat_messages": None,
        "chat_proceed": None,
        "raw_doc_text": "",
        "proposal_state": {},
        "tbd_items": [],
        "tech_stack": {},
        "team_suggestion": {},
        "effort_estimates": {},
        "epics": [],
        "metrics": {},
        "groundedness_score": None,
    }
    result = await _phase_2_init_node(state)
    assert result["phase_status"]["phase_2"] == "in_progress"
    assert result["chat_messages"] == []
    assert result["chat_proceed"] is False


@pytest.mark.asyncio
async def test_phase_2_complete_sets_complete():
    from app.services.workflow import _phase_2_complete_node
    state = {"phase_status": {"phase_2": "in_progress"}}
    result = await _phase_2_complete_node(state)
    assert result["phase_status"]["phase_2"] == "complete"


@pytest.mark.asyncio
async def test_chat_turn_appends_assistant_message():
    mock_chunks = [{"text": "OAuth is required.", "section_hint": "Auth", "chunk_index": 0}]
    mock_tbds = []

    mock_chunk_obj = MagicMock()
    mock_chunk_obj.content = "Based on the document, OAuth is required."

    async def fake_astream(messages):
        yield mock_chunk_obj

    mock_gs_result = MagicMock()
    mock_gs_result.score = 0.9
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=mock_gs_result)
    mock_llm = MagicMock()
    mock_llm.astream = fake_astream
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    state = {
        "project_id": "42",
        "chat_messages": [{"role": "user", "content": "What auth method is used?"}],
        "tbd_items": [],
        "chat_proceed": False,
        "phase_status": {"phase_1": "complete", "phase_2": "in_progress"},
        "raw_doc_text": "",
        "proposal_state": {},
        "tech_stack": {},
        "team_suggestion": {},
        "effort_estimates": {},
        "epics": [],
        "metrics": {},
        "groundedness_score": None,
    }

    with patch("app.services.workflow.retrieve", AsyncMock(return_value=mock_chunks)), \
         patch("app.services.workflow.detect_tbds", AsyncMock(return_value=mock_tbds)), \
         patch("app.services.workflow.get_llm", return_value=mock_llm):
        from app.services.workflow import _chat_turn_node
        result = await _chat_turn_node(state)

    assert len(result["chat_messages"]) == 2
    assert result["chat_messages"][-1]["role"] == "assistant"
    assert "groundedness_score" in result
