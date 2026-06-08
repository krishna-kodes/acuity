import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


async def _collect_sse_events(response) -> list[dict]:
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


def _make_mock_wf(fake_stream_events):
    """Return a mock workflow with async aget_state and a fake astream_events generator."""
    mock_wf = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {"chat_messages": []}

    async def _aget_state(config):
        return mock_state

    mock_wf.aget_state = _aget_state
    mock_wf.astream_events = fake_stream_events
    return mock_wf


# Patch domain classifier to no-op for all chat tests so they don't hit the LLM
_NO_OP_CLASSIFY = patch("app.guardrails.domain_classifier.classify", new=AsyncMock(return_value=None))


@pytest.mark.asyncio
async def test_chat_streams_done_event(async_client):
    async def fake_stream(*args, **kwargs):
        yield {"event": "on_chain_end", "name": "chat_turn", "data": {"output": {}}}

    mock_wf = _make_mock_wf(fake_stream)

    with patch("app.routers.projects.get_workflow", new=AsyncMock(return_value=mock_wf)), _NO_OP_CLASSIFY:
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "hello", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    assert any(e.get("type") == "done" for e in events)


@pytest.mark.asyncio
async def test_chat_streams_token_events(async_client):
    async def fake_stream(*args, **kwargs):
        yield {
            "event": "on_chat_model_stream",
            "name": "chat_response",
            "data": {"chunk": MagicMock(content="Hello")},
        }
        yield {"event": "on_chain_end", "name": "chat_turn", "data": {"output": {}}}

    mock_wf = _make_mock_wf(fake_stream)

    with patch("app.routers.projects.get_workflow", new=AsyncMock(return_value=mock_wf)), _NO_OP_CLASSIFY:
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "hello", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    token_events = [e for e in events if e.get("type") == "token"]
    assert len(token_events) >= 1
    assert token_events[0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_chat_streams_tbd_events(async_client):
    tbds = [{"text": "TBD", "reason": "Explicit placeholder", "level": 1}]

    async def fake_stream(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "chat_turn",
            "data": {"output": {"tbd_items": tbds}},
        }

    mock_wf = _make_mock_wf(fake_stream)

    with patch("app.routers.projects.get_workflow", new=AsyncMock(return_value=mock_wf)), _NO_OP_CLASSIFY:
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "auth is TBD", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    tbd_events = [e for e in events if e.get("type") == "tbds"]
    assert len(tbd_events) == 1
    assert tbd_events[0]["items"][0]["text"] == "TBD"


@pytest.mark.asyncio
async def test_chat_error_returns_error_event(async_client):
    async def fake_stream(*args, **kwargs):
        raise RuntimeError("LLM unavailable")
        yield  # make it a generator

    mock_wf = _make_mock_wf(fake_stream)

    with patch("app.routers.projects.get_workflow", new=AsyncMock(return_value=mock_wf)), _NO_OP_CLASSIFY:
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "hello", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    assert any(e.get("type") == "error" for e in events)
    assert any(e.get("type") == "done" for e in events)


@pytest.mark.asyncio
async def test_chat_domain_classifier_blocks_non_pm(async_client):
    """Layer 1: domain classifier raises HTTP 400 for non-PM queries."""
    from fastapi import HTTPException

    async def raise_400(*args, **kwargs):
        raise HTTPException(
            status_code=400,
            detail="This system only answers questions about project management. "
                   "Your question appears to be about cooking.",
        )

    with patch("app.guardrails.domain_classifier.classify", new=raise_400):
        response = await async_client.post(
            "/api/v1/projects/1/chat",
            json={"message": "How do I make pasta?", "proceed": False},
        )

    assert response.status_code == 400
    assert "project management" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_gate_blocked_streams_message(async_client):
    """Layer 2: gate_blocked SSE event is emitted when retrieval gate fails."""
    async def fake_stream(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "chat_turn",
            "data": {
                "output": {
                    "gate_status": "no_results",
                    "gate_message": "This topic doesn't appear to be covered.",
                }
            },
        }

    mock_wf = _make_mock_wf(fake_stream)

    with patch("app.routers.projects.get_workflow", new=AsyncMock(return_value=mock_wf)), _NO_OP_CLASSIFY:
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "What is the capital of France?", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    gate_events = [e for e in events if e.get("type") == "gate_blocked"]
    assert len(gate_events) == 1
    assert gate_events[0]["status"] == "no_results"


@pytest.mark.asyncio
async def test_chat_groundedness_warning_emitted(async_client):
    """Layer 3: groundedness_warning event emitted when score below threshold."""
    async def fake_stream(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "chat_turn",
            "data": {
                "output": {
                    "groundedness_score": 0.4,
                    "groundedness_reasoning": "Claim not in document.",
                    "groundedness_unsupported_claims": ["The project uses Go."],
                }
            },
        }

    mock_wf = _make_mock_wf(fake_stream)

    with patch("app.routers.projects.get_workflow", new=AsyncMock(return_value=mock_wf)), _NO_OP_CLASSIFY:
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "What language is used?", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    gnd_events = [e for e in events if e.get("type") == "groundedness"]
    warn_events = [e for e in events if e.get("type") == "groundedness_warning"]
    assert len(gnd_events) == 1
    assert gnd_events[0]["flagged"] is True
    assert len(warn_events) == 1
    assert "The project uses Go." in warn_events[0]["unsupported_claims"]
