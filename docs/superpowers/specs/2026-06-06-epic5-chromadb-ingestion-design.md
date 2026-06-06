# Epic 5 (T2): ChromaDB Document Ingestion — Spec

**Goal:** Implement Phase 1 document ingestion: parse PDF/DOCX, chunk with PM-document-aware rules, embed with `text-embedding-3-small`, and store in ChromaDB. Re-upload skips re-embedding.

**Issue:** #36

**Branch:** `feat/epic5-task2-chromadb-ingestion`

---

## Approach

Four async-compatible service modules, each with one responsibility. Background-task safe — orchestrator can be called from FastAPI `BackgroundTasks` and later from Celery/ARQ without rewriting.

```
backend/app/services/
├── parser.py     # parse_pdf(), parse_docx() → ParsedDocument
├── chunker.py    # chunk_document() → list[Chunk]
├── embedder.py   # get_collection(), collection_exists(), embed_and_store()
└── ingestion.py  # ingest_document() orchestrator + dataclasses
```

---

## New packages

Add to `backend/requirements.txt`:
```
chromadb>=0.5.0
openai>=1.30.0
pdfplumber>=0.11.0
python-docx>=1.1.0
tiktoken>=0.7.0
```

---

## Data models (`services/ingestion.py`)

```python
from dataclasses import dataclass, field


@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)
    # tables[table_idx][row_idx][col_idx] = cell text


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
    section_hint: str    # most recent header text seen before this chunk
    token_count: int
```

---

## `services/parser.py`

```python
import pdfplumber
from docx import Document as DocxDocument
from pathlib import Path

from app.services.ingestion import PageContent, ParsedDocument


async def parse_pdf(path: str) -> ParsedDocument:
    pages = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            raw_tables = page.extract_tables() or []
            tables = [
                [[cell or "" for cell in row] for row in table]
                for table in raw_tables
            ]
            pages.append(PageContent(page_number=i + 1, text=text, tables=tables))
    return ParsedDocument(filename=Path(path).name, pages=pages)


async def parse_docx(path: str) -> ParsedDocument:
    doc = DocxDocument(path)
    page_text_lines: list[str] = []
    tables: list[list[list[str]]] = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]
        if tag == "p":
            text = "".join(n.text or "" for n in block.iter())
            if text.strip():
                page_text_lines.append(text)
        elif tag == "tbl":
            rows = []
            for row in block.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"):
                cells = [
                    "".join(n.text or "" for n in cell.iter())
                    for cell in row.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc")
                ]
                rows.append(cells)
            if rows:
                tables.append(rows)

    page = PageContent(
        page_number=1,
        text="\n".join(page_text_lines),
        tables=tables,
    )
    return ParsedDocument(filename=Path(path).name, pages=[page])
```

---

## `services/chunker.py`

```python
import re
import tiktoken

from app.services.ingestion import Chunk, PageContent, ParsedDocument

_ENCODER = tiktoken.get_encoding("cl100k_base")

# Header patterns for PM documents
_HEADER_RE = re.compile(
    r"^(\d+(\.\d+)*\s+\w)"   # numbered: "2.3.1 Title"
    r"|^(#{1,6}\s)"           # markdown: "## Title"
    r"|^[A-Z][A-Z\s]{4,}$"   # ALL CAPS short line
)

# List item patterns
_LIST_RE = re.compile(r"^(\s*[-*•]|\s*\d+[.)]\s)")


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _classify_line(line: str) -> str:
    stripped = line.strip()
    if not stripped:
        return "empty"
    if _HEADER_RE.match(stripped):
        return "header"
    if _LIST_RE.match(stripped):
        return "list_item"
    return "paragraph"


def _table_to_text(table: list[list[str]]) -> str:
    return "\n".join(" | ".join(cell.strip() for cell in row) for row in table)


def _split_to_max(text: str, max_tokens: int) -> list[str]:
    """Split text at sentence boundaries to stay under max_tokens."""
    if _count_tokens(text) <= max_tokens:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts, current = [], ""
    for sentence in sentences:
        candidate = (current + " " + sentence).strip()
        if _count_tokens(candidate) <= max_tokens:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = sentence
    if current:
        parts.append(current)
    return parts or [text[:max_tokens * 4]]  # fallback hard truncation


async def chunk_document(
    parsed: ParsedDocument,
    project_id: str,
    min_tokens: int = 50,
    max_tokens: int = 800,
) -> list[Chunk]:
    raw_chunks: list[Chunk] = []
    chunk_index = 0
    section_hint = ""

    for page in parsed.pages:
        # 1. Extract table chunks first (always atomic)
        for table in page.tables:
            table_text = _table_to_text(table)
            if table_text.strip():
                raw_chunks.append(Chunk(
                    text=table_text,
                    chunk_index=chunk_index,
                    project_id=project_id,
                    detected_type="table",
                    page_number=page.page_number,
                    section_hint=section_hint,
                    token_count=_count_tokens(table_text),
                ))
                chunk_index += 1

        # 2. Chunk page text into structural units
        current_text = ""
        current_type = "paragraph"

        for line in page.text.splitlines():
            line_type = _classify_line(line)
            if line_type == "empty":
                if current_text.strip():
                    raw_chunks.append(Chunk(
                        text=current_text.strip(),
                        chunk_index=chunk_index,
                        project_id=project_id,
                        detected_type=current_type,
                        page_number=page.page_number,
                        section_hint=section_hint,
                        token_count=_count_tokens(current_text.strip()),
                    ))
                    if current_type == "header":
                        section_hint = current_text.strip()
                    chunk_index += 1
                    current_text = ""
                    current_type = "paragraph"
            elif line_type != current_type and current_text.strip():
                raw_chunks.append(Chunk(
                    text=current_text.strip(),
                    chunk_index=chunk_index,
                    project_id=project_id,
                    detected_type=current_type,
                    page_number=page.page_number,
                    section_hint=section_hint,
                    token_count=_count_tokens(current_text.strip()),
                ))
                if current_type == "header":
                    section_hint = current_text.strip()
                chunk_index += 1
                current_text = line
                current_type = line_type
            else:
                current_text = (current_text + "\n" + line).strip() if current_text else line
                current_type = line_type

        if current_text.strip():
            raw_chunks.append(Chunk(
                text=current_text.strip(),
                chunk_index=chunk_index,
                project_id=project_id,
                detected_type=current_type,
                page_number=page.page_number,
                section_hint=section_hint,
                token_count=_count_tokens(current_text.strip()),
            ))
            chunk_index += 1

    # 3. Size normalization: merge tiny, split oversized
    final_chunks: list[Chunk] = []
    pending: Chunk | None = None

    for chunk in raw_chunks:
        if chunk.detected_type == "table":
            if pending:
                final_chunks.append(pending)
                pending = None
            final_chunks.append(chunk)
            continue

        if chunk.token_count < min_tokens:
            if pending is None:
                pending = chunk
            else:
                merged_text = pending.text + "\n" + chunk.text
                pending = Chunk(
                    text=merged_text,
                    chunk_index=pending.chunk_index,
                    project_id=pending.project_id,
                    detected_type=pending.detected_type,
                    page_number=pending.page_number,
                    section_hint=pending.section_hint,
                    token_count=_count_tokens(merged_text),
                )
        elif chunk.token_count > max_tokens:
            if pending:
                final_chunks.append(pending)
                pending = None
            for part in _split_to_max(chunk.text, max_tokens):
                final_chunks.append(Chunk(
                    text=part,
                    chunk_index=len(final_chunks),
                    project_id=chunk.project_id,
                    detected_type=chunk.detected_type,
                    page_number=chunk.page_number,
                    section_hint=chunk.section_hint,
                    token_count=_count_tokens(part),
                ))
        else:
            if pending:
                final_chunks.append(pending)
                pending = None
            final_chunks.append(chunk)

    if pending:
        final_chunks.append(pending)

    # Re-index after normalization
    for i, chunk in enumerate(final_chunks):
        chunk.chunk_index = i

    return final_chunks
```

---

## `services/embedder.py`

```python
import os

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

from app.services.ingestion import Chunk

# Embedding contract — locked by ADR-004, never make these env-configurable
_EMBEDDING_MODEL = "text-embedding-3-small"
_EMBEDDING_DIMS = 1536


def get_collection(project_id: str) -> chromadb.Collection:
    client = chromadb.PersistentClient(path=os.environ["CHROMA_PERSIST_PATH"])
    return client.get_or_create_collection(
        name=f"project_{project_id}",
        metadata={"hnsw:space": "cosine"},
        embedding_function=OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=_EMBEDDING_MODEL,
            dimensions=_EMBEDDING_DIMS,
        ),
    )


def collection_exists(project_id: str) -> bool:
    """Returns True if the collection already has embeddings — cache hit."""
    return get_collection(project_id).count() > 0


async def embed_and_store(chunks: list[Chunk]) -> int:
    """Batch-upsert chunks into ChromaDB. Returns number stored."""
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
```

---

## `services/ingestion.py` (orchestrator)

```python
import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import DocumentStatus
from app.models.project import Document
from app.services.embedder import collection_exists, embed_and_store
from app.services.parser import parse_docx, parse_pdf


async def ingest_document(
    document_id: int,
    project_id: int,        # integer FK matching projects.id
    file_path: str,
    db: Session,
) -> int:
    """Parse, chunk, embed and store a document. Returns chunk count.
    Re-ingestion of the same project_id is a no-op (cache hit).
    """
    chroma_project_id = str(project_id)   # ChromaDB collection name uses str

    # Cache check — skip re-embedding if already done (ADR caching strategy)
    if collection_exists(chroma_project_id):
        from app.services.embedder import get_collection
        return get_collection(project_id).count()

    # Parse
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        parsed = await parse_pdf(file_path)
    elif ext in (".docx", ".doc"):
        parsed = await parse_docx(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Chunk
    from app.services.chunker import chunk_document
    chunks = await chunk_document(
        parsed,
        chroma_project_id,
        min_tokens=settings.chunk_size_min_tokens,
        max_tokens=settings.chunk_size_max_tokens,
    )

    # Embed + store
    stored = await embed_and_store(chunks)

    # Update document status in DB
    db.query(Document).filter(Document.id == document_id).update(
        {"status": DocumentStatus.ready}
    )
    db.commit()

    return stored
```

---

## Tests (`tests/test_ingestion.py`)

```python
# test_parse_pdf: creates a minimal PDF with pdfplumber, asserts pages > 0
# test_parse_docx: creates a minimal DOCX with python-docx, asserts text extracted
# test_chunk_headers: text with numbered headers → chunks with detected_type="header"
# test_chunk_list_items: bulleted list lines → detected_type="list_item"
# test_chunk_tables: page with one table → atomic table chunk, never split
# test_chunk_min_tokens: tiny chunks merged until ≥ min_tokens
# test_chunk_max_tokens: oversized chunk split at sentence boundary
# test_embed_and_store: mock chromadb.PersistentClient, assert upsert called with 17 metadata keys
# test_collection_exists_false: fresh project_id returns False
# test_ingest_cache_hit: call ingest_document twice, embed_and_store called once
# test_ingest_updates_document_status: after ingest, Document.status == DocumentStatus.ready
```

All tests use `unittest.mock.patch` for ChromaDB and OpenAI — no real API calls.

---

## Router update (`routers/projects.py`)

`POST /api/v1/projects/{project_id}/documents` triggers ingestion as a background task:

```python
from fastapi import BackgroundTasks

@router.post("/projects/{project_id}/documents", ...)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> DocumentResponse:
    # Save file to disk
    import os
    os.makedirs("documents", exist_ok=True)
    file_path = f"documents/{project_id}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Create DB record
    doc = Document(project_id=int(project_id), filename=file.filename,
                   status=DocumentStatus.uploaded)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Queue ingestion as background task
    background_tasks.add_task(
        ingest_document, doc.id, project_id, file_path, db
    )

    return DocumentResponse(
        id=str(doc.id), project_id=project_id,
        filename=file.filename, status="uploaded",
        upload_ts=str(doc.upload_ts),
    )
```

---

## Definition of done

- Upload a real PDF → chunks appear in ChromaDB with correct metadata fields
- Re-upload the same project → no new embeddings (cache hit confirmed via `collection.count()`)
- All chunker tests pass: header/list/table/paragraph classification correct
- Token bounds respected: all chunks 50–800 tokens
- `pytest tests/test_ingestion.py` — all tests pass with mocked ChromaDB + OpenAI
- `ruff check .` and `mypy .` pass
