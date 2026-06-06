import json
from unittest.mock import MagicMock, patch

import pytest


async def _collect_sse_events(response) -> list[dict]:
    events = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


@pytest.mark.asyncio
async def test_chat_streams_done_event(async_client):
    mock_wf = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {"chat_messages": []}
    mock_wf.get_state.return_value = mock_state

    async def fake_stream(*args, **kwargs):
        yield {"event": "on_chain_end", "name": "chat_turn", "data": {"output": {}}}

    mock_wf.astream_events = fake_stream

    with patch("app.routers.projects.get_workflow", return_value=mock_wf):
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "hello", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    assert any(e.get("type") == "done" for e in events)


@pytest.mark.asyncio
async def test_chat_streams_token_events(async_client):
    mock_wf = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {"chat_messages": []}
    mock_wf.get_state.return_value = mock_state

    async def fake_stream(*args, **kwargs):
        yield {
            "event": "on_chat_model_stream",
            "name": "ChatGoogleGenerativeAI",
            "data": {"chunk": MagicMock(content="Hello")},
        }
        yield {"event": "on_chain_end", "name": "chat_turn", "data": {"output": {}}}

    mock_wf.astream_events = fake_stream

    with patch("app.routers.projects.get_workflow", return_value=mock_wf):
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
    mock_wf = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {"chat_messages": []}
    mock_wf.get_state.return_value = mock_state

    tbds = [{"text": "TBD", "reason": "Explicit placeholder", "level": 1}]

    async def fake_stream(*args, **kwargs):
        yield {
            "event": "on_chain_end",
            "name": "chat_turn",
            "data": {"output": {"tbd_items": tbds}},
        }

    mock_wf.astream_events = fake_stream

    with patch("app.routers.projects.get_workflow", return_value=mock_wf):
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
    mock_wf = MagicMock()
    mock_state = MagicMock()
    mock_state.values = {"chat_messages": []}
    mock_wf.get_state.return_value = mock_state

    async def fake_stream(*args, **kwargs):
        raise RuntimeError("LLM unavailable")
        yield  # make it a generator

    mock_wf.astream_events = fake_stream

    with patch("app.routers.projects.get_workflow", return_value=mock_wf):
        async with async_client.stream(
            "POST",
            "/api/v1/projects/1/chat",
            json={"message": "hello", "proceed": False},
        ) as response:
            events = await _collect_sse_events(response)

    assert any(e.get("type") == "error" for e in events)
