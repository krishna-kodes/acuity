"""Hybrid RAG retrieval pipeline — BM25 + ChromaDB dense search + RRF fusion + BERT reranker."""

from functools import lru_cache

from langchain_core.messages import HumanMessage
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from app.config import settings
from app.services.llm_factory import get_fast_llm
from app.services.vector_store import vector_store

_REWRITE_PROMPT = (
    "Generate {n} search queries to answer this question from a requirements document.\n"
    "Return one query per line, no numbering or bullets.\n"
    "Question: {query}"
)


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")


async def rewrite_queries(query: str, n: int = 3) -> list[str]:
    """Return the original query plus (n-1) LLM-generated sub-queries."""
    llm = get_fast_llm()
    response = await llm.ainvoke([
        HumanMessage(content=_REWRITE_PROMPT.format(n=n, query=query))
    ])
    content: str = response.content  # type: ignore[assignment]
    lines = [line.strip() for line in content.strip().splitlines() if line.strip()]
    return [query] + lines[: n - 1]


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score for a given rank (0-indexed)."""
    return 1.0 / (k + rank)


# Per-project BM25 cache. Building BM25Okapi loads the whole corpus and
# re-tokenises every chunk; without this, every chat turn (×N sub-queries)
# rebuilds the index from scratch. Validated by chunk count and explicitly
# invalidated on re-embed (see embedder.embed_and_store).
class _BM25Entry:
    __slots__ = ("count", "bm25", "doc_texts", "doc_metadatas")

    def __init__(self, count: int, bm25: BM25Okapi, doc_texts: list, doc_metadatas: list):
        self.count = count
        self.bm25 = bm25
        self.doc_texts = doc_texts
        self.doc_metadatas = doc_metadatas


_bm25_cache: dict[str, _BM25Entry] = {}


def invalidate_bm25(project_id: str) -> None:
    """Drop the cached BM25 index for a project (call after upsert/delete)."""
    _bm25_cache.pop(str(project_id), None)


def _get_bm25(project_id: str) -> _BM25Entry | None:
    """Return a cached/rebuilt BM25 index for the project, or None if empty."""
    pid = str(project_id)
    count = vector_store.count(pid)
    if count == 0:
        _bm25_cache.pop(pid, None)
        return None

    cached = _bm25_cache.get(pid)
    if cached is not None and cached.count == count:
        return cached

    all_docs = vector_store.get_all(pid)
    doc_texts = all_docs["documents"] or []
    doc_metadatas = all_docs["metadatas"] or []
    if not doc_texts:
        _bm25_cache.pop(pid, None)
        return None

    tokenised = [t.lower().split() for t in doc_texts]
    entry = _BM25Entry(count, BM25Okapi(tokenised), doc_texts, doc_metadatas)
    _bm25_cache[pid] = entry
    return entry


async def retrieve_hybrid(
    project_id: str,
    queries: list[str],
    top_k: int = 20,
) -> list[dict]:
    """Fuse dense (ChromaDB) and sparse (BM25) retrieval via RRF."""
    entry = _get_bm25(project_id)
    if entry is None:
        return []
    bm25 = entry.bm25
    doc_texts = entry.doc_texts
    doc_metadatas = entry.doc_metadatas

    rrf_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    for query in queries:
        # Dense retrieval via ChromaDB
        dense_results = vector_store.query(
            project_id, [query], n_results=min(top_k, len(doc_texts))
        )
        dense_docs = dense_results["documents"] or [[]]  # type: ignore[index]
        dense_metas = dense_results["metadatas"] or [[]]  # type: ignore[index]
        for rank, (doc, meta) in enumerate(zip(dense_docs[0], dense_metas[0])):
            cid = f"{meta.get('project_id')}_{meta.get('chunk_index')}"
            rrf_scores[cid] = rrf_scores.get(cid, 0) + _rrf_score(rank)
            chunk_map[cid] = {"text": doc, **meta}

        # Sparse retrieval via BM25
        scores = bm25.get_scores(query.lower().split())
        sorted_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        for rank, idx in enumerate(sorted_idx[:top_k]):
            meta = doc_metadatas[idx]
            cid = f"{meta.get('project_id')}_{meta.get('chunk_index')}"
            rrf_scores[cid] = rrf_scores.get(cid, 0) + _rrf_score(rank)
            chunk_map.setdefault(cid, {"text": doc_texts[idx], **meta})

    top = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunk_map[cid] for cid, _ in top]


def _diversify_by_section(chunks: list[dict], max_per_section: int = 3) -> list[dict]:
    """Cap per-section contribution so one section can't fill all reranker slots.

    Chunks must arrive sorted by RRF score (best first); order preserved.
    """
    section_counts: dict[str, int] = {}
    result = []
    for chunk in chunks:
        section = chunk.get("section_hint") or "_unknown"
        count = section_counts.get(section, 0)
        if count < max_per_section:
            result.append(chunk)
            section_counts[section] = count + 1
    return result


def rerank(query: str, chunks: list[dict], top_n: int = 4) -> tuple[list[dict], list[float]]:
    """Re-rank chunks using a BERT cross-encoder.

    Returns (top_n_chunks, all_candidate_scores) so callers can log retrieval quality.
    """
    if not chunks:
        return [], []
    reranker = _get_reranker()
    pairs: list[tuple[str, str]] = [(query, c["text"]) for c in chunks]
    scores = reranker.predict(pairs)  # type: ignore[arg-type]
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_n]], list(scores)


async def retrieve(
    project_id: str,
    query: str,
    top_k: int | None = None,
    top_n: int | None = None,
) -> tuple[list[dict], list[float], int]:
    """Full RAG pipeline: query rewriting → hybrid retrieval → BERT reranking.

    Returns (reranked_chunks, all_reranker_scores, n_candidates_before_rerank).
    """
    if not query.strip():
        return [], [], 0
    top_k = top_k or settings.top_k_retrieval
    top_n = top_n or settings.top_n_rerank
    queries = await rewrite_queries(query, n=settings.query_rewrite_count)
    candidates = await retrieve_hybrid(project_id, queries, top_k)
    # Cap any single section to max(2, top_n-1) slots so one section can't fill all reranker slots
    candidates = _diversify_by_section(candidates, max_per_section=max(2, top_n - 1))
    chunks, scores = rerank(query, candidates, top_n)
    return chunks, scores, len(candidates)
