# Phase 2 Chat RAG — Spec

**Goal:** Implement the Phase 2 chat loop — hybrid RAG retrieval, TBD detection, SSE streaming — as a LangGraph looping node with SqliteSaver persistence.

**Issue:** #45 (Phase 2 implementation for E2E demo)

**Branch:** `feat/epic6-phase2-chat-rag`

---

## Architecture

Single LangGraph graph with a looping `chat_turn` node. The PM sends messages; the graph pauses at `interrupt_after=["chat_turn"]` after each turn. When the PM clicks "Proceed", the state update `chat_proceed=True` advances to `phase_3_stack`.

```
phase_2_init → chat_turn ⟲ (loops per message)
                        ↓ chat_proceed=True
               phase_2_complete → phase_3_stack → ...
```

---

## New files

```
backend/app/services/
├── rag.py              ← hybrid retrieval + reranker
└── tbd_detection.py    ← Level 1 regex + Level 2 LLM (batched, deduplicated)

backend/tests/
├── test_rag.py
├── test_tbd_detection.py
├── test_chat_node.py
└── test_chat_endpoint.py
```

**Modified:**
- `backend/app/services/workflow.py` — replace `_phase_2_chat_node` with `_phase_2_init_node`, `_chat_turn_node`, `_phase_2_complete_node` + routing
- `backend/app/routers/projects.py` — add `POST /projects/{id}/chat` SSE endpoint
- `backend/requirements.txt` — add `rank-bm25>=0.2.2`, `sentence-transformers>=3.0.0`

---

## State additions

```python
class ProjectState(TypedDict):
    # ... all existing fields unchanged ...
    chat_messages: list   # [{"role": "user"|"assistant", "content": str}]
    chat_proceed: bool    # True = PM clicked "Proceed" → exits loop
```

`tbd_items` already exists — chat turns populate it incrementally.

---

## `services/rag.py`

```python
import asyncio
from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from app.config import settings
from app.services.embedder import get_collection
from app.services.llm_factory import get_fast_llm

# Module-level singleton — loaded once, ~500MB, local inference
@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


_REWRITE_PROMPT = """Generate {n} search queries to answer this question from a requirements document.
Return one query per line, no numbering or bullets.
Question: {query}"""


async def rewrite_queries(query: str, n: int = 3) -> list[str]:
    """Generate n sub-queries via fast LLM for multi-query retrieval."""
    llm = get_fast_llm()
    response = await llm.ainvoke([
        HumanMessage(content=_REWRITE_PROMPT.format(n=n, query=query))
    ])
    lines = [l.strip() for l in response.content.strip().splitlines() if l.strip()]
    return [query] + lines[:n - 1]  # original query always first


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank)


async def retrieve_hybrid(
    project_id: str,
    queries: list[str],
    top_k: int = 20,
) -> list[dict]:
    """Hybrid retrieval: dense (ChromaDB) + sparse (BM25), merged via RRF."""
    collection = get_collection(project_id)
    all_docs = collection.get(include=["documents", "metadatas"])
    doc_texts = all_docs["documents"] or []
    doc_metadatas = all_docs["metadatas"] or []

    if not doc_texts:
        return []

    # BM25 sparse index over stored chunks
    tokenised = [t.lower().split() for t in doc_texts]
    bm25 = BM25Okapi(tokenised)

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    for query in queries:
        # Dense retrieval
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

        # Sparse BM25 retrieval
        scores = bm25.get_scores(query.lower().split())
        sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for rank, idx in enumerate(sorted_idx[:top_k]):
            meta = doc_metadatas[idx]
            cid = f"{meta.get('project_id')}_{meta.get('chunk_index')}"
            rrf_scores[cid] = rrf_scores.get(cid, 0) + _rrf_score(rank)
            chunk_map.setdefault(cid, {"text": doc_texts[idx], **meta})

    # Sort by RRF score, return top_k
    top = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunk_map[cid] for cid, _ in top]


def rerank(query: str, chunks: list[dict], top_n: int = 4) -> list[dict]:
    """BERT cross-encoder reranking: score (query, chunk) pairs, return top_n."""
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
    """Full pipeline: rewrite → hybrid retrieve → rerank."""
    top_k = top_k or settings.top_k_retrieval
    top_n = top_n or settings.top_n_rerank
    queries = await rewrite_queries(query, n=settings.query_rewrite_count)
    candidates = await retrieve_hybrid(project_id, queries, top_k)
    return rerank(query, candidates, top_n)
```

---

## `services/tbd_detection.py`

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
Examples of vague: "should be fast", "must be reliable", "easy to use", "as needed".
Return ONLY a JSON object matching this schema:
{{"items": [{{"text": "<vague phrase>", "reason": "<why it's vague>", "level": 2}}]}}
Return {{"items": []}} if no vague statements found.

Document chunks:
{chunks}"""


class TBDItem(BaseModel):
    text: str
    reason: str
    level: Literal[1, 2]


class TBDDetectionResult(BaseModel):
    items: list[TBDItem]


def detect_level_1(text: str) -> list[dict]:
    """Regex-based explicit TBD detection — zero latency."""
    results = []
    for match in _L1_RE.finditer(text):
        results.append({
            "text": match.group(),
            "reason": "Explicit placeholder or unknown",
            "level": 1,
        })
    return results


async def detect_level_2_batch(
    chunks: list[dict],
    known_tbds: set[str] | None = None,
) -> list[dict]:
    """LLM-based vague statement detection — one batched call, structured output."""
    if not chunks:
        return []
    known = known_tbds or set()
    combined = "\n\n---\n\n".join(c["text"] for c in chunks)
    llm = get_fast_llm()
    structured_llm = llm.with_structured_output(TBDDetectionResult)
    result: TBDDetectionResult = await structured_llm.ainvoke([
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
    """Combined Level 1 + Level 2 detection, deduplicated against known items."""
    known = known_tbds or set()
    level1 = [t for t in detect_level_1(query) if t["text"] not in known]
    level2 = await detect_level_2_batch(chunks, known_tbds=known)
    all_tbds = level1 + level2
    # Final dedup by text
    return list({t["text"]: t for t in all_tbds}.values())
```

---

## `workflow.py` changes

Replace `_phase_2_chat_node` with three nodes + routing:

```python
# Add to ProjectState
class ProjectState(TypedDict):
    # ... existing fields ...
    chat_messages: list
    chat_proceed: bool

# New nodes
async def _phase_2_init_node(state: ProjectState) -> dict:
    _require_phase_complete(state, 2)
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "in_progress"
    return {"phase_status": ps, "chat_messages": [], "chat_proceed": False}


@with_retry()
async def _chat_turn_node(state: ProjectState) -> dict:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    from app.services.rag import retrieve
    from app.services.tbd_detection import detect_tbds
    from app.services.llm_factory import get_llm, get_fast_llm
    from app.config import settings

    messages = list(state.get("chat_messages") or [])
    project_id = state["project_id"]
    last_user = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    # RAG retrieval
    chunks = await retrieve(project_id, last_user)
    context = "\n\n".join(
        f"[{c.get('section_hint', '')}] {c['text']}" for c in chunks
    )

    # TBD detection (batch, deduplicated)
    known = {t.get("text", "") for t in (state.get("tbd_items") or [])}
    new_tbds = await detect_tbds(last_user, chunks, known_tbds=known)

    # LLM response — use astream so astream_events emits on_chat_model_stream tokens
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

    # Groundedness check (CLAUDE.md GROUNDEDNESS_THRESHOLD=0.7)
    groundedness_score = None
    if settings.groundedness_check_enabled:
        judge = get_fast_llm().with_structured_output(GroundednessResult)
        gs: GroundednessResult = await judge.ainvoke([
            HumanMessage(content=GROUNDEDNESS_JUDGE_PROMPT.format(
                retrieved_chunks=context,
                llm_response=response_content,
            ))
        ])
        groundedness_score = gs.score

    messages.append({"role": "assistant", "content": response_content})
    return {
        "chat_messages": messages,
        "tbd_items": list(state.get("tbd_items") or []) + new_tbds,
        "groundedness_score": groundedness_score,
    }


async def _phase_2_complete_node(state: ProjectState) -> dict:
    ps = dict(state.get("phase_status") or {})
    ps["phase_2"] = "complete"
    return {"phase_status": ps}


def _chat_routing(state: ProjectState) -> str:
    """Pure routing function — no state mutation."""
    return "phase_2_complete" if state.get("chat_proceed") else "chat_turn"


# Groundedness schema
class GroundednessResult(BaseModel):
    score: float
    reasoning: str
    unsupported_claims: list[str]

GROUNDEDNESS_JUDGE_PROMPT = """System: You are an evaluation judge. Answer only with a JSON object.
User:
  Context: {retrieved_chunks}
  Response: {llm_response}
  Question: Is every factual claim in the Response directly supported by the Context?
  Score 0-1 where 1 = fully grounded, 0 = contains unsupported claims.
  Output: {{"score": float, "reasoning": str, "unsupported_claims": list[str]}}"""
```

Graph wiring (replace old `phase_2_chat` node):
```python
workflow.add_node("phase_2_init",     _phase_2_init_node)
workflow.add_node("chat_turn",        _chat_turn_node)
workflow.add_node("phase_2_complete", _phase_2_complete_node)

workflow.set_entry_point("phase_2_init")
workflow.add_edge("phase_2_init", "chat_turn")
workflow.add_conditional_edges("chat_turn", _chat_routing)
workflow.add_edge("phase_2_complete", "phase_3_stack")

interrupt_after=["chat_turn"]  # replaces "phase_2_chat" in the list
```

Add three fields to `ProjectState` and `_EMPTY_STATE` in `workflow.py`:
```python
# ProjectState additions
chat_messages: list        # default []
chat_proceed: bool         # default False
groundedness_score: float | None  # default None

# _EMPTY_STATE additions
"chat_messages": [],
"chat_proceed": False,
"groundedness_score": None,
```

---

## Chat endpoint

Add `ChatRequest` to `backend/app/schemas/project.py` (follows existing schema pattern):
```python
class ChatRequest(BaseModel):
    message: str
    proceed: bool = False
```

# In routers/projects.py
@router.post("/projects/{project_id}/chat", summary="Phase 2 RAG chat turn (SSE)")
async def chat(
    project_id: str,
    body: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    import json
    from app.services.workflow import get_workflow
    from app.config import settings

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

                if etype == "on_chat_model_stream" and name != "GroundednessResult":
                    token = event["data"]["chunk"].content
                    if token:
                        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

                elif etype == "on_chain_end" and name == "chat_turn":
                    output = event["data"].get("output", {})
                    if tbds := output.get("tbd_items"):
                        yield f"data: {json.dumps({'type': 'tbds', 'items': tbds})}\n\n"
                    if (gs := output.get("groundedness_score")) is not None:
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

## Tests

```
backend/tests/
├── test_rag.py              # retrieve pipeline with mocked ChromaDB, BM25, CrossEncoder, LLM
├── test_tbd_detection.py    # Level 1 regex (no mocks), Level 2 with mocked LLM
├── test_chat_node.py        # _chat_turn_node, _chat_routing, _phase_2_complete_node
└── test_chat_endpoint.py    # POST /chat SSE stream with mocked workflow
```

Key tests:
- `test_rrf_merge_combines_dense_and_sparse` — assert RRF scores sum correctly
- `test_reranker_returns_top_n` — mock CrossEncoder, assert len == top_n
- `test_detect_level_1_explicit` — assert TBD/TODO/N/A detected
- `test_detect_level_1_no_false_positives` — assert "quickly" not flagged
- `test_detect_level_2_deduplicates_known` — known TBD text skipped
- `test_chat_routing_loops` — `_chat_routing({"chat_proceed": False}) == "chat_turn"`
- `test_chat_routing_advances` — `_chat_routing({"chat_proceed": True}) == "phase_2_complete"`
- `test_chat_streams_token_events` — SSE stream contains at least one `{"type": "token"}` event
- `test_chat_streams_done_event` — last SSE event is `{"type": "done"}`

---

## New packages

```
rank-bm25>=0.2.2
sentence-transformers>=3.0.0
```

---

## Definition of done

- `POST /api/v1/projects/{id}/chat` streams tokens via SSE
- LangGraph graph loops correctly: multiple messages stay in Phase 2; `proceed=True` advances to Phase 3
- TBDs detected and emitted per turn, deduplicated across turns
- Groundedness score emitted when `GROUNDEDNESS_CHECK_ENABLED=true`
- `pytest tests/test_rag.py tests/test_tbd_detection.py tests/test_chat_node.py tests/test_chat_endpoint.py` — all pass
- `ruff check .` and `mypy .` pass
