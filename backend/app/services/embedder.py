"""Embedding + storage layer — delegates all vector-store access to the adapter.

Phase nodes and RAG must use `app.services.vector_store.vector_store` directly.
These helpers exist for the ingestion path and back-compat.
"""

from app.services.ingestion import Chunk
from app.services.vector_store import vector_store


def collection_exists(project_id: str) -> bool:
    return vector_store.exists(project_id)


def delete_collection(project_id: str) -> None:
    vector_store.delete(project_id)
    _invalidate_bm25(project_id)


def _invalidate_bm25(project_id: str) -> None:
    # Lazy import avoids an import cycle (rag imports vector_store, not embedder).
    from app.services.rag import invalidate_bm25
    invalidate_bm25(project_id)


def collection_count(project_id: str) -> int:
    return vector_store.count(project_id)


async def embed_and_store(chunks: list[Chunk]) -> int:
    if not chunks:
        return 0
    vector_store.upsert(
        project_id=chunks[0].project_id,
        ids=[f"{c.project_id}_{c.chunk_index}" for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[{
            "project_id": c.project_id,
            "chunk_index": c.chunk_index,
            "detected_type": c.detected_type,
            "page_number": c.page_number,
            "section_hint": c.section_hint,
            "token_count": c.token_count,
        } for c in chunks],
    )
    _invalidate_bm25(chunks[0].project_id)
    return len(chunks)
