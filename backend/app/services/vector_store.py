"""Vector store abstraction (ADR-003).

ChromaDB is the MVP vector store but the architecture treats it as swappable.
All collection access goes through `VectorStoreAdapter` so a post-MVP migration
to Qdrant or Pinecone is a single adapter swap. Phase nodes and the RAG pipeline
must never touch a ChromaDB client/collection directly — call `vector_store.*`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from app.config import settings

# Locked by ADR-004 — never make these env-configurable
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMS = 1536


class VectorStoreAdapter(ABC):
    """Interface for project-scoped chunk storage + retrieval."""

    @abstractmethod
    def upsert(
        self,
        project_id: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None: ...

    @abstractmethod
    def query(self, project_id: str, query_texts: list[str], n_results: int) -> dict: ...

    @abstractmethod
    def get_all(self, project_id: str) -> dict: ...

    @abstractmethod
    def count(self, project_id: str) -> int: ...

    @abstractmethod
    def exists(self, project_id: str) -> bool: ...

    @abstractmethod
    def delete(self, project_id: str) -> None: ...


class ChromaAdapter(VectorStoreAdapter):
    """MVP implementation backed by ChromaDB `PersistentClient` (ADR-003)."""

    @staticmethod
    def _collection_name(project_id: str) -> str:
        return f"project_{project_id}"

    def _client(self) -> chromadb.ClientAPI:
        # Never `chromadb.Client()` — persistence is required (ADR-003).
        return chromadb.PersistentClient(path=settings.chroma_persist_path)

    def _collection(self, project_id: str) -> chromadb.Collection:
        return self._client().get_or_create_collection(
            name=self._collection_name(project_id),
            metadata={"hnsw:space": "cosine"},
            embedding_function=OpenAIEmbeddingFunction(  # type: ignore[arg-type]
                api_key=settings.openai_api_key,
                model_name=_EMBEDDING_MODEL,
                dimensions=_EMBEDDING_DIMS,
            ),
        )

    def upsert(
        self,
        project_id: str,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        self._collection(project_id).upsert(
            ids=ids, documents=documents, metadatas=metadatas
        )

    def query(self, project_id: str, query_texts: list[str], n_results: int) -> dict:
        return self._collection(project_id).query(
            query_texts=query_texts,
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    def get_all(self, project_id: str) -> dict:
        return self._collection(project_id).get(include=["documents", "metadatas"])

    def count(self, project_id: str) -> int:
        return self._collection(project_id).count()

    def exists(self, project_id: str) -> bool:
        client = self._client()
        name = self._collection_name(project_id)
        if name not in [c.name for c in client.list_collections()]:
            return False
        return client.get_collection(name).count() > 0

    def delete(self, project_id: str) -> None:
        try:
            self._client().delete_collection(self._collection_name(project_id))
        except Exception:
            pass


# Module-level singleton — the one place that constructs a vector-store client.
vector_store: VectorStoreAdapter = ChromaAdapter()
