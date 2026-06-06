from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_rewrite_queries_returns_original_plus_subqueries():
    mock_response = MagicMock()
    mock_response.content = "What are the auth requirements?\nHow should login work?"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.rag.get_fast_llm", return_value=mock_llm):
        from app.services.rag import rewrite_queries
        result = await rewrite_queries("authentication", n=3)

    assert result[0] == "authentication"  # original always first
    assert len(result) == 3


@pytest.mark.asyncio
async def test_retrieve_hybrid_returns_merged_results(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "documents": ["Auth requires OAuth.", "Login page design."],
        "metadatas": [
            {"project_id": "1", "chunk_index": 0, "section_hint": "Auth"},
            {"project_id": "1", "chunk_index": 1, "section_hint": "UI"},
        ],
    }
    mock_collection.query.return_value = {
        "documents": [["Auth requires OAuth."]],
        "metadatas": [[{"project_id": "1", "chunk_index": 0, "section_hint": "Auth"}]],
        "distances": [[0.1]],
    }

    with patch("app.services.rag.get_collection", return_value=mock_collection), \
         patch("app.services.embedder.OpenAIEmbeddingFunction"):
        from app.services.rag import retrieve_hybrid
        result = await retrieve_hybrid("1", ["authentication"], top_k=5)

    assert len(result) >= 1
    assert all("text" in r for r in result)


def test_rerank_returns_top_n():
    chunks = [
        {"text": "OAuth is used for authentication.", "chunk_index": 0},
        {"text": "The sky is blue.", "chunk_index": 1},
        {"text": "Users log in with email and password.", "chunk_index": 2},
        {"text": "Database schema requires indexing.", "chunk_index": 3},
    ]
    mock_scores = [0.9, 0.1, 0.8, 0.2]

    with patch("app.services.rag._get_reranker") as mock_reranker_fn:
        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = mock_scores
        mock_reranker_fn.return_value = mock_reranker

        from app.services.rag import rerank
        result = rerank("authentication", chunks, top_n=2)

    assert len(result) == 2
    assert result[0]["chunk_index"] == 0  # score 0.9 is highest
    assert result[1]["chunk_index"] == 2  # score 0.8 is second


@pytest.mark.asyncio
async def test_retrieve_full_pipeline(tmp_path, monkeypatch):
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_response = MagicMock()
    mock_response.content = "query 1\nquery 2"
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    mock_collection = MagicMock()
    mock_collection.get.return_value = {
        "documents": ["OAuth required.", "JWT tokens used."],
        "metadatas": [
            {"project_id": "42", "chunk_index": 0, "section_hint": "Auth"},
            {"project_id": "42", "chunk_index": 1, "section_hint": "Auth"},
        ],
    }
    mock_collection.query.return_value = {
        "documents": [["OAuth required."]],
        "metadatas": [[{"project_id": "42", "chunk_index": 0, "section_hint": "Auth"}]],
        "distances": [[0.1]],
    }
    mock_scores = [0.9, 0.8]

    with patch("app.services.rag.get_fast_llm", return_value=mock_llm), \
         patch("app.services.rag.get_collection", return_value=mock_collection), \
         patch("app.services.embedder.OpenAIEmbeddingFunction"), \
         patch("app.services.rag._get_reranker") as mock_reranker_fn:
        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = mock_scores
        mock_reranker_fn.return_value = mock_reranker

        from app.services.rag import retrieve
        result = await retrieve("42", "authentication", top_k=5, top_n=2)

    assert len(result) <= 2
    assert all("text" in r for r in result)
