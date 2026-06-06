# Phase 2 Chat RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 chat — hybrid RAG retrieval, TBD detection, LangGraph looping node, and SSE streaming endpoint — as a prerequisite for the E2E demo.

**Architecture:** `services/rag.py` (ChromaDB + BM25 → RRF → BERT reranker) and `services/tbd_detection.py` (regex + batched LLM) feed a new `chat_turn` node in `workflow.py`. The node loops via conditional edge until `chat_proceed=True`. The chat endpoint streams LangGraph events as SSE.

**Tech Stack:** Python 3.11, LangGraph, LangChain (google-genai), rank-bm25, sentence-transformers, FastAPI StreamingResponse

**Spec:** `docs/superpowers/specs/2026-06-07-phase2-chat-rag-design.md`

---

## File map

```
backend/
├── requirements.txt                 ← add rank-bm25>=0.2.2, sentence-transformers>=3.0.0
├── app/
│   ├── services/
│   │   ├── rag.py                   ← Task 1
│   │   └── tbd_detection.py         ← Task 2
│   ├── schemas/project.py           ← Task 4 (add ChatRequest)
│   ├── routers/projects.py          ← Task 4 (add /chat endpoint)
│   └── services/workflow.py         ← Task 3 (replace phase_2 stub)
└── tests/
    ├── test_rag.py                  ← Task 1
    ├── test_tbd_detection.py        ← Task 2
    ├── test_chat_node.py            ← Task 3
    └── test_chat_endpoint.py        ← Task 4
```

---

## Task 1: Hybrid RAG service

**Branch:** `feat/epic6-phase2-chat-rag`

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/rag.py`
- Create: `backend/tests/test_rag.py`

---

- [ ] **Step 1: Branch from main**

```bash
cd /path/to/acuity
git checkout main && git pull origin main
git checkout -b feat/epic6-phase2-chat-rag
```

---

- [ ] **Step 2: Add packages to `backend/requirements.txt`**

```
rank-bm25>=0.2.2
sentence-transformers>=3.0.0
```

Install:
```bash
cd /path/to/acuity/backend
source .venv/bin/activate
pip install "rank-bm25>=0.2.2" "sentence-transformers>=3.0.0"
```

---

- [ ] **Step 3: Write failing RAG tests first (TDD)**

Create `backend/tests/test_rag.py`:

```python
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
```

---

- [ ] **Step 4: Run tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_rag.py -v 2>&1 | tail -10
```

Expected: `ImportError` — `app.services.rag` does not exist.

---

- [ ] **Step 5: Create `backend/app/services/rag.py`**

```python
import asyncio
from functools import lru_cache

from langchain_core.messages import HumanMessage
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from app.config import settings
from app.services.embedder import get_collection
from app.services.llm_factory import get_fast_llm

_REWRITE_PROMPT = """Generate {n} search queries to answer this question from a requirements document.
Return one query per line, no numbering or bullets.
Question: {query}"""


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


async def rewrite_queries(query: str, n: int = 3) -> list[str]:
    llm = get_fast_llm()
    response = await llm.ainvoke([
        HumanMessage(content=_REWRITE_PROMPT.format(n=n, query=query))
    ])
    lines = [line.strip() for line in response.content.strip().splitlines() if line.strip()]
    return [query] + lines[: n - 1]


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


async def retrieve_hybrid(
    project_id: str,
    queries: list[str],
    top_k: int = 20,
) -> list[dict]:
    collection = get_collection(project_id)
    all_docs = collection.get(include=["documents", "metadatas"])
    doc_texts = all_docs["documents"] or []
    doc_metadatas = all_docs["metadatas"] or []

    if not doc_texts:
        return []

    tokenised = [t.lower().split() for t in doc_texts]
    bm25 = BM25Okapi(tokenised)

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    for query in queries:
        dense_results = collection.query(
            query_texts=[query],
            n_results=min(top_k, len(doc_texts)),
            include=["documents", "metadatas", "distances"],
        )
        for rank, (doc, meta) in enumerate(
            zip(dense_results["documents"][0], dense_results["metadatas"][0])
        ):
            cid = f"{meta.get('project_id')}_{meta.get('chunk_index')}"
            rrf_scores[cid] = rrf_scores.get(cid, 0) + _rrf_score(rank)
            chunk_map[cid] = {"text": doc, **meta}

        scores = bm25.get_scores(query.lower().split())
        sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for rank, idx in enumerate(sorted_idx[:top_k]):
            meta = doc_metadatas[idx]
            cid = f"{meta.get('project_id')}_{meta.get('chunk_index')}"
            rrf_scores[cid] = rrf_scores.get(cid, 0) + _rrf_score(rank)
            chunk_map.setdefault(cid, {"text": doc_texts[idx], **meta})

    top = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunk_map[cid] for cid, _ in top]


def rerank(query: str, chunks: list[dict], top_n: int = 4) -> list[dict]:
    if not chunks:
        return []
    reranker = _get_reranker()
    pairs = [(query, c["text"]) for c in chunks]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_n]]


async def retrieve(
    project_id: str,
    query: str,
    top_k: int | None = None,
    top_n: int | None = None,
) -> list[dict]:
    top_k = top_k or settings.top_k_retrieval
    top_n = top_n or settings.top_n_rerank
    queries = await rewrite_queries(query, n=settings.query_rewrite_count)
    candidates = await retrieve_hybrid(project_id, queries, top_k)
    return rerank(query, candidates, top_n)
```

---

- [ ] **Step 6: Run RAG tests — verify 4 pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_rag.py -v
```

Expected: 4 tests PASS.

---

- [ ] **Step 7: Run full suite — confirm nothing broken**

```bash
python -m pytest tests/ -v --ignore=tests/test_rag.py 2>&1 | tail -5
```

---

- [ ] **Step 8: Commit**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E6-#85a] hybrid RAG service — BM25 + ChromaDB + RRF + BERT reranker"
```

---

## Task 2: TBD detection service

**Files:**
- Create: `backend/app/services/tbd_detection.py`
- Create: `backend/tests/test_tbd_detection.py`

---

- [ ] **Step 1: Write failing TBD detection tests**

Create `backend/tests/test_tbd_detection.py`:

```python
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
    mock_result = MagicMock()
    mock_result.items = [
        MagicMock(text="should be fast", reason="No measurable threshold", level=2, model_dump=lambda: {"text": "should be fast", "reason": "No measurable threshold", "level": 2})
    ]
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
    mock_result = MagicMock()
    mock_result.items = [
        MagicMock(
            text="should be fast",
            reason="No measurable threshold",
            level=2,
            model_dump=lambda: {"text": "should be fast", "reason": "No measurable threshold", "level": 2}
        )
    ]
    mock_structured_llm = MagicMock()
    mock_structured_llm.ainvoke = AsyncMock(return_value=mock_result)
    mock_llm = MagicMock()
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)

    with patch("app.services.tbd_detection.get_fast_llm", return_value=mock_llm):
        from app.services.tbd_detection import detect_level_2_batch
        chunks = [{"text": "The system should be fast."}]
        result = await detect_level_2_batch(
            chunks, known_tbds={"should be fast"}  # already known
        )

    assert result == []  # filtered out


@pytest.mark.asyncio
async def test_detect_tbds_empty_chunks():
    from app.services.tbd_detection import detect_tbds
    result = await detect_tbds("hello", [], known_tbds=set())
    assert result == []
```

---

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_tbd_detection.py -v 2>&1 | tail -10
```

Expected: `ImportError` — `app.services.tbd_detection` does not exist.

---

- [ ] **Step 3: Create `backend/app/services/tbd_detection.py`**

```python
import re
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.services.llm_factory import get_fast_llm

_L1_RE = re.compile(
    r"\b(TBD|TODO|N/?A|to be determined|to be confirmed|TBC|UNKNOWN|unclear|not yet defined)\b",
    re.IGNORECASE,
)

_L2_PROMPT = """You are reviewing requirements document chunks for quality issues.
Identify any statements that are vague, unmeasurable, or lack clear criteria.
Examples: "should be fast", "must be reliable", "easy to use", "as needed".
Return ONLY a JSON object: {{"items": [{{"text": str, "reason": str, "level": 2}}]}}
Return {{"items": []}} if none found.

Document chunks:
{chunks}"""


class _TBDItem(BaseModel):
    text: str
    reason: str
    level: Literal[1, 2]


class _TBDResult(BaseModel):
    items: list[_TBDItem]


def detect_level_1(text: str) -> list[dict]:
    return [
        {"text": m.group(), "reason": "Explicit placeholder or unknown", "level": 1}
        for m in _L1_RE.finditer(text)
    ]


async def detect_level_2_batch(
    chunks: list[dict],
    known_tbds: set[str] | None = None,
) -> list[dict]:
    if not chunks:
        return []
    known = known_tbds or set()
    combined = "\n\n---\n\n".join(c["text"] for c in chunks)
    llm = get_fast_llm()
    structured = llm.with_structured_output(_TBDResult)
    result: _TBDResult = await structured.ainvoke([
        HumanMessage(content=_L2_PROMPT.format(chunks=combined))
    ])
    return [
        item.model_dump()
        for item in result.items
        if item.text not in known
    ]


async def detect_tbds(
    query: str,
    chunks: list[dict],
    known_tbds: set[str] | None = None,
) -> list[dict]:
    known = known_tbds or set()
    level1 = [t for t in detect_level_1(query) if t["text"] not in known]
    level2 = await detect_level_2_batch(chunks, known_tbds=known)
    all_tbds = level1 + level2
    return list({t["text"]: t for t in all_tbds}.values())
```

---

- [ ] **Step 4: Run TBD tests — verify 7 pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_tbd_detection.py -v
```

Expected: 7 tests PASS.

---

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -5
```

---

- [ ] **Step 6: Commit**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E6-#85b] TBD detection — Level 1 regex + Level 2 batched LLM"
```

---

## Task 3: LangGraph workflow — Phase 2 loop

**Files:**
- Modify: `backend/app/services/workflow.py`
- Create: `backend/tests/test_chat_node.py`

---

- [ ] **Step 1: Write failing workflow tests**

Create `backend/tests/test_chat_node.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_chat_routing_loops_without_proceed():
    from app.services.workflow import _chat_routing
    result = _chat_routing({"chat_proceed": False, "project_id": "1"})
    assert result == "chat_turn"


def test_chat_routing_loops_when_proceed_missing():
    from app.services.workflow import _chat_routing
    result = _chat_routing({"project_id": "1"})  # no chat_proceed key
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
    mock_chunk = MagicMock()
    mock_chunk.content = "Based on the document, OAuth is required."

    mock_llm = MagicMock()
    mock_llm.astream = AsyncMock(return_value=aiter_mock([mock_chunk]))

    mock_gs_result = MagicMock()
    mock_gs_result.score = 0.9
    mock_structured = MagicMock()
    mock_structured.ainvoke = AsyncMock(return_value=mock_gs_result)
    mock_llm.with_structured_output = MagicMock(return_value=mock_structured)

    state = {
        "project_id": "42",
        "chat_messages": [{"role": "user", "content": "What auth method is used?"}],
        "tbd_items": [],
        "chat_proceed": False,
        "phase_status": {"phase_1": "complete", "phase_2": "in_progress"},
    }

    with patch("app.services.workflow.retrieve", AsyncMock(return_value=mock_chunks)), \
         patch("app.services.workflow.detect_tbds", AsyncMock(return_value=mock_tbds)), \
         patch("app.services.workflow.get_llm", return_value=mock_llm):
        from app.services.workflow import _chat_turn_node
        result = await _chat_turn_node(state)

    assert len(result["chat_messages"]) == 2
    assert result["chat_messages"][-1]["role"] == "assistant"
    assert "groundedness_score" in result


# Helper for async iteration in tests
async def aiter_mock(items):
    for item in items:
        yield item
```

---

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_chat_node.py -v 2>&1 | tail -10
```

Expected: `ImportError` — `_chat_routing`, `_phase_2_init_node`, etc. do not exist yet.

---

- [ ] **Step 3: Update `ProjectState` and `_EMPTY_STATE` in `workflow.py`**

Add three fields to `ProjectState`:
```python
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
    phase_status: dict
    chat_messages: list        # NEW
    chat_proceed: bool         # NEW
    groundedness_score: float | None  # NEW
```

Add to `_EMPTY_STATE`:
```python
_EMPTY_STATE: ProjectState = {
    # ... existing fields unchanged ...
    "chat_messages": [],
    "chat_proceed": False,
    "groundedness_score": None,
}
```

---

- [ ] **Step 4: Add new nodes and routing to `workflow.py`**

Add these imports at the top of `workflow.py`:
```python
from pydantic import BaseModel
```

Add the groundedness schema and prompt (paste verbatim):
```python
class _GroundednessResult(BaseModel):
    score: float
    reasoning: str
    unsupported_claims: list[str]


_GROUNDEDNESS_PROMPT = """System: You are an evaluation judge. Answer only with a JSON object.
User:
  Context: {context}
  Response: {response}
  Question: Is every factual claim in the Response directly supported by the Context?
  Score 0-1 where 1 = fully grounded, 0 = contains unsupported claims.
  Output: {{"score": float, "reasoning": str, "unsupported_claims": list[str]}}"""
```

Replace `_phase_2_chat_node` with three new functions:

```python
async def _phase_2_init_node(state: ProjectState) -> dict[str, Any]:
    _require_phase_complete(state, 2)
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "in_progress"
    return {"phase_status": ps, "chat_messages": [], "chat_proceed": False}


@with_retry()
async def _chat_turn_node(state: ProjectState) -> dict[str, Any]:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from app.services.rag import retrieve
    from app.services.tbd_detection import detect_tbds
    from app.services.llm_factory import get_llm
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
        response_parts.append(chunk.content)
    response_content = "".join(response_parts)

    groundedness_score = None
    if settings.groundedness_check_enabled:
        judge = llm.with_structured_output(_GroundednessResult)
        gs: _GroundednessResult = await judge.ainvoke([
            HumanMessage(content=_GROUNDEDNESS_PROMPT.format(
                context=context, response=response_content
            ))
        ])
        groundedness_score = gs.score

    messages.append({"role": "assistant", "content": response_content})
    return {
        "chat_messages": messages,
        "tbd_items": list(state.get("tbd_items") or []) + new_tbds,
        "groundedness_score": groundedness_score,
    }


async def _phase_2_complete_node(state: ProjectState) -> dict[str, Any]:
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "complete"
    return {"phase_status": ps}


def _chat_routing(state: ProjectState) -> str:
    return "phase_2_complete" if state.get("chat_proceed") else "chat_turn"
```

---

- [ ] **Step 5: Update `build_workflow()` in `workflow.py`**

Replace the old `workflow.add_node("phase_2_chat", _phase_2_chat_node)` and related edges with:

```python
workflow.add_node("phase_2_init",     _phase_2_init_node)
workflow.add_node("chat_turn",        _chat_turn_node)
workflow.add_node("phase_2_complete", _phase_2_complete_node)
workflow.add_node("phase_3_stack",    _phase_3_stack_node)
workflow.add_node("phase_4_team",     _phase_4_team_node)
workflow.add_node("phase_5_estimate", _phase_5_estimate_node)
workflow.add_node("phase_6_epics",    _phase_6_epics_node)

workflow.set_entry_point("phase_2_init")
workflow.add_edge("phase_2_init", "chat_turn")
workflow.add_conditional_edges("chat_turn", _chat_routing)
workflow.add_edge("phase_2_complete", "phase_3_stack")
workflow.add_edge("phase_3_stack",    "phase_4_team")
workflow.add_edge("phase_4_team",     "phase_5_estimate")
workflow.add_edge("phase_5_estimate", "phase_6_epics")
workflow.add_edge("phase_6_epics",    END)

return workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["chat_turn", "phase_3_stack", "phase_4_team", "phase_5_estimate"],
)
```

---

- [ ] **Step 6: Run workflow tests — verify 6 pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_chat_node.py -v
```

Expected: 6 tests PASS.

---

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -5
```

---

- [ ] **Step 8: Commit**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E6-#85c] LangGraph Phase 2 loop — chat_turn node + conditional routing"
```

---

## Task 4: Chat endpoint (SSE) + PR

**Files:**
- Modify: `backend/app/schemas/project.py` (add ChatRequest)
- Modify: `backend/app/routers/projects.py` (add /chat endpoint)
- Create: `backend/tests/test_chat_endpoint.py`

---

- [ ] **Step 1: Write failing endpoint tests**

Create `backend/tests/test_chat_endpoint.py`:

```python
import json
from unittest.mock import AsyncMock, MagicMock, patch

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
```

---

- [ ] **Step 2: Add `async_client` fixture to `backend/tests/conftest.py`**

The existing `conftest.py` has a sync `client` fixture. SSE streaming requires `httpx.AsyncClient`. Open `backend/tests/conftest.py` and append:

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def async_client():
    app.dependency_overrides[get_db] = lambda: None
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

Also add `anyio` to `requirements-dev.txt` if not present (needed for async pytest fixtures with httpx):
```
anyio[trio]>=4.0.0
```

---

- [ ] **Step 3: Run tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
pip install "anyio[trio]>=4.0.0"
python -m pytest tests/test_chat_endpoint.py -v 2>&1 | tail -10
```

Expected: errors — `ChatRequest` not in schemas, `/chat` route missing.

---

- [ ] **Step 4: Add `ChatRequest` to `backend/app/schemas/project.py`**

Open `backend/app/schemas/project.py` and add at the end:

```python
class ChatRequest(BaseModel):
    message: str
    proceed: bool = False
```

---

- [ ] **Step 5: Add the `/chat` endpoint to `backend/app/routers/projects.py`**

Add these imports at the top of `projects.py` (if not already present):
```python
import json
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
from app.schemas.project import ChatRequest
from app.services.workflow import get_workflow
```

Add the endpoint after the existing `sync_to_github` route:

```python
@router.post(
    "/projects/{project_id}/chat",
    summary="Phase 2 RAG chat turn (SSE)",
)
async def chat(
    project_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    wf = get_workflow()
    config = {"configurable": {"thread_id": project_id}}

    existing = wf.get_state(config)
    history = list(existing.values.get("chat_messages") or [])
    history.append({"role": "user", "content": body.message})

    state_update = {"chat_messages": history, "chat_proceed": body.proceed}

    async def event_generator():
        try:
            async for event in wf.astream_events(
                state_update, config=config, version="v2"
            ):
                etype = event["event"]
                name = event.get("name", "")

                if etype == "on_chat_model_stream" and "GroundednessResult" not in name:
                    token = event["data"]["chunk"].content
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                elif etype == "on_chain_end" and name == "chat_turn":
                    output = event["data"].get("output", {})
                    if tbds := output.get("tbd_items"):
                        yield f"data: {json.dumps({'type': 'tbds', 'items': tbds})}\n\n"
                    if (gs := output.get("groundedness_score")) is not None:
                        from app.config import settings
                        yield f"data: {json.dumps({'type': 'groundedness', 'score': gs, 'flagged': gs < settings.groundedness_threshold})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

---

- [ ] **Step 6: Run endpoint tests — verify 4 pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_chat_endpoint.py -v
```

Expected: 4 tests PASS.

---

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -10
```

Expected: all tests pass.

---

- [ ] **Step 8: Lint and type check**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
ruff check .
mypy .
```

Fix any issues before committing.

---

- [ ] **Step 9: Commit and push**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E6-#85] Phase 2 chat RAG — SSE endpoint + LangGraph loop

Closes #85"
git push -u origin feat/epic6-phase2-chat-rag
```

---

- [ ] **Step 10: Open PR**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E6-#85] Phase 2 chat RAG — hybrid retrieval, TBD detection, SSE" \
  --body "## Summary
Implements Phase 2 chat loop as a LangGraph looping node with SSE streaming. Prerequisite for the E2E demo (#45).

## Related issues
Closes #85

## Changes
- \`services/rag.py\` — hybrid RAG: ChromaDB + BM25 → RRF → BERT reranker
- \`services/tbd_detection.py\` — Level 1 regex + Level 2 batched LLM structured output
- \`services/workflow.py\` — Phase 2 loop: phase_2_init → chat_turn ⟲ → phase_2_complete
- \`routers/projects.py\` — POST /projects/{id}/chat SSE endpoint
- \`schemas/project.py\` — ChatRequest schema
- 4 new test files (test_rag, test_tbd_detection, test_chat_node, test_chat_endpoint)

## Dependency check
- [x] Epic 5 + E6-T1/T2/T3 merged — backend and frontend complete
- [x] Pulled latest main and rebased before opening PR
- [x] Checked for new issues from the other dev

## Testing
- [x] \`pytest tests/\` — all tests pass
- [x] \`ruff check .\` passes
- [x] \`mypy .\` passes"
```

---

- [ ] **Step 11: Merge and clean up**

```bash
gh pr merge --repo krishna-kodes/acuity --squash --delete-branch
git checkout main && git pull origin main
git branch -d feat/epic6-phase2-chat-rag 2>/dev/null || true
git fetch --prune
```
