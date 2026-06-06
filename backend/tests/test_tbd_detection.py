from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_detect_level_1_explicit_tbd():
    from app.services.tbd_detection import detect_level_1
    result = detect_level_1("The response time is TBD.")
    assert len(result) == 1
    assert result[0]["level"] == 1
    assert result[0]["text"] == "TBD"


def test_detect_level_1_multiple_matches():
    from app.services.tbd_detection import detect_level_1
    result = detect_level_1("Auth is TBD. Error handling is TODO.")
    assert len(result) == 2


def test_detect_level_1_no_false_positives():
    from app.services.tbd_detection import detect_level_1
    result = detect_level_1("The system must respond within 200ms.")
    assert result == []


def test_detect_level_1_case_insensitive():
    from app.services.tbd_detection import detect_level_1
    result = detect_level_1("Status: tbd")
    assert len(result) == 1


@pytest.mark.asyncio
async def test_detect_level_2_batch_returns_structured():
    mock_item = MagicMock()
    mock_item.text = "should be fast"
    mock_item.reason = "No measurable threshold"
    mock_item.level = 2
    mock_item.model_dump = lambda: {"text": "should be fast", "reason": "No measurable threshold", "level": 2}

    mock_result = MagicMock()
    mock_result.items = [mock_item]

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

    with patch("app.services.tbd_detection.get_fast_llm", return_value=mock_llm):
        from app.services.tbd_detection import detect_level_2_batch
        chunks = [{"text": "The system should be fast and reliable."}]
        result = await detect_level_2_batch(chunks, known_tbds=set())

    assert len(result) == 1
    assert result[0]["level"] == 2


@pytest.mark.asyncio
async def test_detect_level_2_deduplicates_known():
    mock_item = MagicMock()
    mock_item.text = "should be fast"
    mock_item.reason = "No measurable threshold"
    mock_item.level = 2
    mock_item.model_dump = lambda: {"text": "should be fast", "reason": "No measurable threshold", "level": 2}

    mock_result = MagicMock()
    mock_result.items = [mock_item]

    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

    with patch("app.services.tbd_detection.get_fast_llm", return_value=mock_llm):
        from app.services.tbd_detection import detect_level_2_batch
        chunks = [{"text": "The system should be fast."}]
        result = await detect_level_2_batch(
            chunks, known_tbds={"should be fast"}
        )

    assert result == []


@pytest.mark.asyncio
async def test_detect_tbds_empty_chunks():
    from app.services.tbd_detection import detect_tbds
    result = await detect_tbds("hello", [], known_tbds=set())
    assert result == []
