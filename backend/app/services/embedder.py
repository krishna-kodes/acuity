import os

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from app.services.ingestion import Chunk

# Locked by ADR-004 — never make these env-configurable
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMS = 1536


def get_collection(project_id: str) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])
    return client.get_or_create_collection(
        name=f"project_{project_id}",
        metadata={"hnsw:space": "cosine"},
        embedding_function=OpenAIEmbeddingFunction(  # type: ignore[arg-type]
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=_EMBEDDING_MODEL,
            dimensions=_EMBEDDING_DIMS,
        ),
    )


def collection_exists(project_id: str) -> bool:
    client = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])
    existing = [c.name for c in client.list_collections()]
    collection_name = f"project_{project_id}"
    if collection_name not in existing:
        return False
    return client.get_collection(collection_name).count() > 0


async def embed_and_store(chunks: list[Chunk]) -> int:
    if not chunks:
        return 0
    collection = get_collection(chunks[0].project_id)
    collection.upsert(
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
    return len(chunks)
