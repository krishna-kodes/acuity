# Epic 5 (T2): ChromaDB Document Ingestion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1 document ingestion — parse PDF/DOCX, chunk with PM-document-aware rules, embed with `text-embedding-3-small`, and store in ChromaDB. Re-upload skips re-embedding.

**Architecture:** Four async-compatible service modules (`parser`, `chunker`, `embedder`, `ingestion`). Dataclasses live in `ingestion.py`; other modules import from it using lazy imports inside functions to avoid circular dependencies. The router triggers ingestion via FastAPI `BackgroundTasks`.

**Tech Stack:** Python 3.11, pdfplumber, python-docx, tiktoken, chromadb, openai, FastAPI BackgroundTasks

**Spec:** `docs/superpowers/specs/2026-06-06-epic5-chromadb-ingestion-design.md`

---

## File map

```
backend/
├── requirements.txt                          ← add 5 new packages
├── app/
│   ├── services/
│   │   ├── ingestion.py                      ← CREATE: dataclasses + orchestrator
│   │   ├── parser.py                         ← CREATE: parse_pdf, parse_docx
│   │   ├── chunker.py                        ← CREATE: chunk_document
│   │   └── embedder.py                       ← CREATE: get_collection, embed_and_store
│   └── routers/
│       └── projects.py                       ← MODIFY: upload_document stub → real impl
└── tests/
    └── test_ingestion.py                     ← CREATE: 11 tests
```

---

## Task 1: Packages + dataclasses + parser

**Branch:** `feat/epic5-task2-chromadb-ingestion`

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/ingestion.py` (dataclasses only — orchestrator added in Task 4)
- Create: `backend/app/services/parser.py`
- Create: `backend/tests/test_ingestion.py` (parser tests only)

---

- [ ] **Step 1: Branch from main**

```bash
cd /path/to/acuity
git checkout main && git pull origin main
git checkout -b feat/epic5-task2-chromadb-ingestion
```

---

- [ ] **Step 2: Add packages to `backend/requirements.txt`**

```
fastapi==0.111.0
uvicorn[standard]==0.30.0
sqlalchemy==2.0.30
pydantic-settings==2.2.1
python-multipart==0.0.9
alembic==1.13.1
httpx>=0.27.0
fastmcp>=2.0.0
chromadb>=0.5.0
openai>=1.30.0
pdfplumber>=0.11.0
python-docx>=1.1.0
tiktoken>=0.7.0
```

Install:
```bash
cd /path/to/acuity/backend
source .venv/bin/activate
pip install pdfplumber python-docx tiktoken chromadb openai
```

---

- [ ] **Step 3: Write failing parser tests**

Create `backend/tests/test_ingestion.py`:

```python
import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Parser tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_pdf_extracts_text():
    """parse_pdf returns a ParsedDocument with at least one page of text."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "This is a requirement.\nSystem shall support OAuth."
    mock_page.extract_tables.return_value = []

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("pdfplumber.open", return_value=mock_pdf):
        from app.services.parser import parse_pdf
        result = await parse_pdf("/fake/doc.pdf")

    assert result.filename == "doc.pdf"
    assert len(result.pages) == 1
    assert "OAuth" in result.pages[0].text
    assert result.pages[0].page_number == 1


@pytest.mark.asyncio
async def test_parse_pdf_extracts_tables():
    """parse_pdf converts pdfplumber tables to list[list[list[str]]]."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_page.extract_tables.return_value = [
        [["Feature", "Priority"], ["OAuth", "High"], [None, "Low"]]
    ]

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("pdfplumber.open", return_value=mock_pdf):
        from app.services.parser import parse_pdf
        result = await parse_pdf("/fake/doc.pdf")

    assert len(result.pages[0].tables) == 1
    assert result.pages[0].tables[0][0] == ["Feature", "Priority"]
    assert result.pages[0].tables[0][2] == ["", "Low"]  # None replaced with ""


@pytest.mark.asyncio
async def test_parse_docx_extracts_text(tmp_path):
    """parse_docx returns a ParsedDocument with extracted paragraph text."""
    from docx import Document as DocxDocument
    docx_path = tmp_path / "test.docx"
    doc = DocxDocument()
    doc.add_paragraph("1. Authentication Requirements")
    doc.add_paragraph("The system shall support OAuth 2.0.")
    doc.save(str(docx_path))

    from app.services.parser import parse_docx
    result = await parse_docx(str(docx_path))

    assert result.filename == "test.docx"
    assert "OAuth" in result.pages[0].text
```

---

- [ ] **Step 4: Run tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
pip install pytest-asyncio
python -m pytest tests/test_ingestion.py -v 2>&1 | tail -15
```

Expected: `ImportError` — `app.services.parser` does not exist yet.

---

- [ ] **Step 5: Create `backend/app/services/ingestion.py`** (dataclasses only)

```python
from dataclasses import dataclass, field


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
```

---

- [ ] **Step 6: Create `backend/app/services/parser.py`**

```python
from pathlib import Path

import pdfplumber
from docx import Document as DocxDocument

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
    text_lines: list[str] = []
    tables: list[list[list[str]]] = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]
        if tag == "p":
            text = "".join(n.text or "" for n in block.iter())
            if text.strip():
                text_lines.append(text.strip())
        elif tag == "tbl":
            ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            rows = []
            for row in block.iter(f"{{{ns}}}tr"):
                cells = [
                    "".join(n.text or "" for n in cell.iter())
                    for cell in row.iter(f"{{{ns}}}tc")
                ]
                rows.append(cells)
            if rows:
                tables.append(rows)

    page = PageContent(
        page_number=1,
        text="\n".join(text_lines),
        tables=tables,
    )
    return ParsedDocument(filename=Path(path).name, pages=[page])
```

---

- [ ] **Step 7: Run parser tests — verify they pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py::test_parse_pdf_extracts_text \
    tests/test_ingestion.py::test_parse_pdf_extracts_tables \
    tests/test_ingestion.py::test_parse_docx_extracts_text -v
```

Expected: 3 tests PASS.

---

- [ ] **Step 8: Run full test suite — confirm nothing broken**

```bash
python -m pytest tests/ -v --ignore=tests/test_ingestion.py
```

Expected: all pre-existing tests pass.

---

- [ ] **Step 9: Commit**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E5-T2a] parser service + dataclasses + parser tests"
```

---

## Task 2: Chunker

**Files:**
- Create: `backend/app/services/chunker.py`
- Modify: `backend/tests/test_ingestion.py` (add chunker tests)

---

- [ ] **Step 1: Add chunker tests to `backend/tests/test_ingestion.py`**

Append these tests to the existing file:

```python
# ── Chunker tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chunk_detects_numbered_header():
    """Lines matching '2.3 Title' are classified as headers."""
    from app.services.chunker import chunk_document
    from app.services.ingestion import PageContent, ParsedDocument

    parsed = ParsedDocument(
        filename="req.pdf",
        pages=[PageContent(
            page_number=1,
            text="2.3 Authentication Requirements\nThe system shall support OAuth 2.0.",
            tables=[],
        )],
    )
    chunks = await chunk_document(parsed, "proj_1")
    types = [c.detected_type for c in chunks]
    assert "header" in types


@pytest.mark.asyncio
async def test_chunk_detects_list_items():
    """Lines starting with '- ' or '* ' are classified as list_items."""
    from app.services.chunker import chunk_document
    from app.services.ingestion import PageContent, ParsedDocument

    parsed = ParsedDocument(
        filename="req.pdf",
        pages=[PageContent(
            page_number=1,
            text="- The system shall support OAuth 2.0\n- Response time < 200ms\n* Must handle 1000 concurrent users",
            tables=[],
        )],
    )
    chunks = await chunk_document(parsed, "proj_1")
    types = [c.detected_type for c in chunks]
    assert "list_item" in types


@pytest.mark.asyncio
async def test_chunk_table_is_atomic():
    """A table always produces exactly one chunk regardless of size."""
    from app.services.chunker import chunk_document
    from app.services.ingestion import PageContent, ParsedDocument

    big_table = [["Col A", "Col B"]] + [["val", "val"] for _ in range(100)]
    parsed = ParsedDocument(
        filename="req.pdf",
        pages=[PageContent(page_number=1, text="", tables=[big_table])],
    )
    chunks = await chunk_document(parsed, "proj_1")
    table_chunks = [c for c in chunks if c.detected_type == "table"]
    assert len(table_chunks) == 1


@pytest.mark.asyncio
async def test_chunk_token_bounds():
    """All non-table chunks are within [min_tokens, max_tokens]."""
    from app.services.chunker import chunk_document
    from app.services.ingestion import PageContent, ParsedDocument

    long_text = " ".join(["The system shall handle requests efficiently."] * 50)
    parsed = ParsedDocument(
        filename="req.pdf",
        pages=[PageContent(page_number=1, text=long_text, tables=[])],
    )
    chunks = await chunk_document(parsed, "proj_1", min_tokens=50, max_tokens=200)
    for chunk in chunks:
        if chunk.detected_type != "table":
            assert chunk.token_count >= 50, f"Chunk too small: {chunk.token_count}"
            assert chunk.token_count <= 200, f"Chunk too large: {chunk.token_count}"


@pytest.mark.asyncio
async def test_chunk_section_hint_propagates():
    """section_hint on non-header chunks equals the most recent header text."""
    from app.services.chunker import chunk_document
    from app.services.ingestion import PageContent, ParsedDocument

    parsed = ParsedDocument(
        filename="req.pdf",
        pages=[PageContent(
            page_number=1,
            text="2. Functional Requirements\n\nThe system shall support OAuth 2.0.\n\nThe system shall log all actions.",
            tables=[],
        )],
    )
    chunks = await chunk_document(parsed, "proj_1")
    non_headers = [c for c in chunks if c.detected_type != "header"]
    assert all(c.section_hint == "2. Functional Requirements" for c in non_headers)
```

---

- [ ] **Step 2: Run chunker tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py -k "chunk" -v 2>&1 | tail -10
```

Expected: `ImportError` — `app.services.chunker` does not exist.

---

- [ ] **Step 3: Create `backend/app/services/chunker.py`**

```python
import re

import tiktoken

from app.services.ingestion import Chunk, ParsedDocument

_ENCODER = tiktoken.get_encoding("cl100k_base")

_HEADER_RE = re.compile(
    r"^(\d+(\.\d+)*\s+\w)"   # numbered: "2.3.1 Title"
    r"|^(#{1,6}\s)"           # markdown: "## Title"
    r"|^[A-Z][A-Z\s]{4,}$"   # ALL CAPS line
)
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
    if _count_tokens(text) <= max_tokens:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts: list[str] = []
    current = ""
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
    return parts or [text[: max_tokens * 4]]


async def chunk_document(
    parsed: ParsedDocument,
    project_id: str,
    min_tokens: int = 50,
    max_tokens: int = 800,
) -> list[Chunk]:
    raw: list[Chunk] = []
    idx = 0
    section_hint = ""

    for page in parsed.pages:
        # Tables first — always atomic
        for table in page.tables:
            table_text = _table_to_text(table)
            if table_text.strip():
                raw.append(Chunk(
                    text=table_text,
                    chunk_index=idx,
                    project_id=project_id,
                    detected_type="table",
                    page_number=page.page_number,
                    section_hint=section_hint,
                    token_count=_count_tokens(table_text),
                ))
                idx += 1

        # Text — group consecutive same-type lines
        current_text = ""
        current_type = "paragraph"

        def flush(t: str, dt: str) -> None:
            nonlocal idx, section_hint
            if not t.strip():
                return
            raw.append(Chunk(
                text=t.strip(),
                chunk_index=idx,
                project_id=project_id,
                detected_type=dt,
                page_number=page.page_number,
                section_hint=section_hint,
                token_count=_count_tokens(t.strip()),
            ))
            if dt == "header":
                section_hint = t.strip()
            idx += 1

        for line in page.text.splitlines():
            lt = _classify_line(line)
            if lt == "empty":
                flush(current_text, current_type)
                current_text = ""
                current_type = "paragraph"
            elif lt != current_type and current_text.strip():
                flush(current_text, current_type)
                current_text = line
                current_type = lt
            else:
                current_text = (current_text + "\n" + line).strip() if current_text else line
                current_type = lt

        flush(current_text, current_type)

    # Size normalization
    final: list[Chunk] = []
    pending: Chunk | None = None

    for chunk in raw:
        if chunk.detected_type == "table":
            if pending:
                final.append(pending)
                pending = None
            final.append(chunk)
            continue

        if chunk.token_count < min_tokens:
            if pending is None:
                pending = chunk
            else:
                merged = pending.text + "\n" + chunk.text
                pending = Chunk(
                    text=merged,
                    chunk_index=pending.chunk_index,
                    project_id=pending.project_id,
                    detected_type=pending.detected_type,
                    page_number=pending.page_number,
                    section_hint=pending.section_hint,
                    token_count=_count_tokens(merged),
                )
        elif chunk.token_count > max_tokens:
            if pending:
                final.append(pending)
                pending = None
            for part in _split_to_max(chunk.text, max_tokens):
                final.append(Chunk(
                    text=part,
                    chunk_index=len(final),
                    project_id=chunk.project_id,
                    detected_type=chunk.detected_type,
                    page_number=chunk.page_number,
                    section_hint=chunk.section_hint,
                    token_count=_count_tokens(part),
                ))
        else:
            if pending:
                final.append(pending)
                pending = None
            final.append(chunk)

    if pending:
        final.append(pending)

    for i, c in enumerate(final):
        c.chunk_index = i

    return final
```

---

- [ ] **Step 4: Run chunker tests — verify they pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py -k "chunk" -v
```

Expected: 5 tests PASS.

---

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass (existing + 3 parser + 5 chunker).

---

- [ ] **Step 6: Commit**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E5-T2b] chunker service + PM-document-aware chunking tests"
```

---

## Task 3: Embedder

**Files:**
- Create: `backend/app/services/embedder.py`
- Modify: `backend/tests/test_ingestion.py` (add embedder tests)

---

- [ ] **Step 1: Add embedder tests to `backend/tests/test_ingestion.py`**

Append these tests:

```python
# ── Embedder tests ───────────────────────────────────────────────────────────

def test_collection_exists_false(tmp_path, monkeypatch):
    """Returns False when the project has no embeddings yet."""
    import chromadb
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("chromadb.utils.embedding_functions.OpenAIEmbeddingFunction"):
        from app.services.embedder import collection_exists
        # Fresh tmp_path — no embeddings
        assert collection_exists("new_project") is False


@pytest.mark.asyncio
async def test_embed_and_store_calls_upsert(tmp_path, monkeypatch):
    """embed_and_store calls collection.upsert with correct metadata keys."""
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    from app.services.ingestion import Chunk

    chunks = [
        Chunk(
            text="The system shall support OAuth 2.0.",
            chunk_index=0,
            project_id="42",
            detected_type="paragraph",
            page_number=1,
            section_hint="2. Auth",
            token_count=10,
        )
    ]

    mock_collection = MagicMock()
    mock_collection.upsert = MagicMock()

    with patch("app.services.embedder.chromadb.PersistentClient") as mock_client, \
         patch("app.services.embedder.OpenAIEmbeddingFunction"):
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        from app.services.embedder import embed_and_store
        stored = await embed_and_store(chunks)

    assert stored == 1
    mock_collection.upsert.assert_called_once()
    call_kwargs = mock_collection.upsert.call_args
    metadata = call_kwargs.kwargs["metadatas"][0]
    assert metadata["project_id"] == "42"
    assert metadata["detected_type"] == "paragraph"
    assert metadata["section_hint"] == "2. Auth"
    assert metadata["token_count"] == 10


@pytest.mark.asyncio
async def test_embed_and_store_empty_returns_zero():
    """embed_and_store with empty list returns 0 without calling ChromaDB."""
    from app.services.embedder import embed_and_store
    result = await embed_and_store([])
    assert result == 0
```

---

- [ ] **Step 2: Run embedder tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py -k "embed or collection" -v 2>&1 | tail -10
```

Expected: `ImportError` — `app.services.embedder` does not exist.

---

- [ ] **Step 3: Create `backend/app/services/embedder.py`**

```python
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
        embedding_function=OpenAIEmbeddingFunction(
            api_key=os.environ["OPENAI_API_KEY"],
            model_name=_EMBEDDING_MODEL,
            dimensions=_EMBEDDING_DIMS,
        ),
    )


def collection_exists(project_id: str) -> bool:
    return get_collection(project_id).count() > 0


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
```

---

- [ ] **Step 4: Run embedder tests — verify they pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py -k "embed or collection" -v
```

Expected: 3 tests PASS.

---

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -v
```

Expected: all tests pass (existing + 3 parser + 5 chunker + 3 embedder).

---

- [ ] **Step 6: Commit**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E5-T2c] embedder service (ChromaDB + OpenAI text-embedding-3-small)"
```

---

## Task 4: Ingestion orchestrator + router + PR

**Files:**
- Modify: `backend/app/services/ingestion.py` (add `ingest_document` function)
- Modify: `backend/app/routers/projects.py` (replace upload stub)
- Modify: `backend/tests/test_ingestion.py` (add integration + cache tests)

---

- [ ] **Step 1: Add integration tests to `backend/tests/test_ingestion.py`**

Append these tests:

```python
# ── Ingestion orchestrator tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ingest_document_cache_hit(tmp_path, monkeypatch):
    """Second call to ingest_document with same project_id is a no-op."""
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    call_count = {"n": 0}

    async def fake_embed(chunks):
        call_count["n"] += 1
        return len(chunks)

    mock_collection = MagicMock()
    mock_collection.count.return_value = 5  # already has embeddings

    with patch("chromadb.PersistentClient") as mock_client, \
         patch("chromadb.utils.embedding_functions.OpenAIEmbeddingFunction"), \
         patch("app.services.ingestion.embed_and_store", fake_embed):
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        from importlib import reload
        import app.services.ingestion as ing_mod
        reload(ing_mod)

        result = await ing_mod.ingest_document(
            document_id=1, project_id=99, file_path="/fake/doc.pdf", db=MagicMock()
        )

    assert result == 5          # returned existing count
    assert call_count["n"] == 0  # embed_and_store never called


@pytest.mark.asyncio
async def test_ingest_document_updates_status(tmp_path, monkeypatch):
    """ingest_document sets Document.status = ready after ingestion."""
    monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_collection.count.return_value = 0  # no existing embeddings

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "The system shall support OAuth 2.0 login."
    mock_page.extract_tables.return_value = []
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("chromadb.PersistentClient") as mock_client, \
         patch("chromadb.utils.embedding_functions.OpenAIEmbeddingFunction"), \
         patch("pdfplumber.open", return_value=mock_pdf):
        mock_client.return_value.get_or_create_collection.return_value = mock_collection

        from importlib import reload
        import app.services.ingestion as ing_mod
        reload(ing_mod)

        await ing_mod.ingest_document(
            document_id=7, project_id=3, file_path="/fake/req.pdf", db=mock_db
        )

    mock_db.commit.assert_called_once()
```

---

- [ ] **Step 2: Run integration tests — verify they fail**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py -k "ingest" -v 2>&1 | tail -10
```

Expected: `ImportError` or `AttributeError` — `ingest_document` not yet defined.

---

- [ ] **Step 3: Add `ingest_document` to `backend/app/services/ingestion.py`**

Append to the existing file (after the dataclasses):

```python
import os
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import DocumentStatus
from app.models.project import Document


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
```

---

- [ ] **Step 4: Run integration tests — verify they pass**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/test_ingestion.py -k "ingest" -v
```

Expected: 2 tests PASS.

---

- [ ] **Step 5: Update `upload_document` in `backend/app/routers/projects.py`**

Replace the current stub:
```python
@router.post("/projects/{project_id}/documents", ...)
def upload_document(...):
    # current stub
```

With the real implementation:

```python
import os

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import DocumentStatus
from app.models.project import Document
from app.schemas.document import DocumentResponse
from app.services.ingestion import ingest_document


@router.post(
    "/projects/{project_id}/documents",
    summary="Upload requirements document",
    response_model=DocumentResponse,
    status_code=201,
)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    os.makedirs("documents", exist_ok=True)
    file_path = f"documents/{project_id}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = Document(
        project_id=int(project_id),
        filename=file.filename or "unknown",
        status=DocumentStatus.uploaded,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(
        ingest_document, doc.id, int(project_id), file_path, db
    )

    return DocumentResponse(
        id=str(doc.id),
        project_id=project_id,
        filename=doc.filename,
        status=doc.status.value,
        upload_ts=str(doc.upload_ts),
    )
```

---

- [ ] **Step 6: Run full test suite**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: all tests pass. Count: 30 pre-existing + 3 parser + 5 chunker + 3 embedder + 2 integration = **43 tests**.

---

- [ ] **Step 7: Lint and type check**

```bash
cd /path/to/acuity/backend
source .venv/bin/activate
ruff check .
mypy .
```

Fix any issues before committing.

---

- [ ] **Step 8: Commit and push**

```bash
cd /path/to/acuity
git add backend/
git commit -m "feat: [E5-T2] ChromaDB ingestion pipeline — parser, chunker, embedder, orchestrator

Closes #36"
git push -u origin feat/epic5-task2-chromadb-ingestion
```

---

- [ ] **Step 9: Open PR**

```bash
gh pr create \
  --repo krishna-kodes/acuity \
  --base main \
  --title "[E5-T2] ChromaDB ingestion — parse, chunk, embed, store" \
  --body "## Summary
Implements Phase 1 document ingestion as four async service modules. PDF/DOCX parsed with pdfplumber/python-docx, chunked with PM-document-aware rules (headers, list items, atomic tables), embedded with text-embedding-3-small (1536 dims, cosine), stored in ChromaDB PersistentClient. Re-upload skips re-embedding.

## Related issues
Closes #36

## Changes
- \`services/ingestion.py\` — dataclasses + ingest_document orchestrator
- \`services/parser.py\` — parse_pdf + parse_docx
- \`services/chunker.py\` — PM-aware chunker (header/list/table/paragraph)
- \`services/embedder.py\` — get_collection + embed_and_store (ADR-004 locked)
- \`routers/projects.py\` — upload_document stub replaced with real impl + BackgroundTasks
- \`tests/test_ingestion.py\` — 13 tests (mocked ChromaDB + OpenAI)

## Dependency check
- [x] E5-T1 merged — Document model exists
- [x] Pulled latest main and rebased before opening PR
- [x] Checked for new issues from the other dev

## Testing
- [x] \`pytest tests/\` — 43 tests pass
- [x] \`ruff check .\` passes
- [x] \`mypy .\` passes"
```

---

- [ ] **Step 10: Merge and clean up**

```bash
gh pr merge --repo krishna-kodes/acuity --squash --delete-branch
git checkout main && git pull origin main
git branch -d feat/epic5-task2-chromadb-ingestion 2>/dev/null || true
git fetch --prune
```
