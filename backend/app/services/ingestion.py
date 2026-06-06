from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import DocumentStatus
from app.models.project import Document


@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    filename: str
    pages: list[PageContent]


@dataclass
class Chunk:
    text: str
    chunk_index: int
    project_id: str
    detected_type: str   # "paragraph" | "header" | "table" | "list_item"
    page_number: int
    section_hint: str
    token_count: int


async def ingest_document(
    document_id: int,
    project_id: int,
    file_path: str,
    db: Session,
) -> int:
    """Parse, chunk, embed and store a document. Returns chunk count.
    Re-ingestion of the same project_id is a no-op (cache hit).
    """
    from app.services.embedder import collection_exists, embed_and_store, get_collection

    chroma_project_id = str(project_id)

    if collection_exists(chroma_project_id):
        return get_collection(chroma_project_id).count()

    from app.services.parser import parse_docx, parse_pdf

    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        parsed = await parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        parsed = await parse_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    from app.services.chunker import chunk_document

    chunks = await chunk_document(
        parsed,
        chroma_project_id,
        min_tokens=settings.chunk_size_min_tokens,
        max_tokens=settings.chunk_size_max_tokens,
    )

    stored = await embed_and_store(chunks)

    db.query(Document).filter(Document.id == document_id).update(
        {"status": DocumentStatus.ready}
    )
    db.commit()

    return stored
