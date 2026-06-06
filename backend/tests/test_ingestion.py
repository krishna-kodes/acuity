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

    long_para = "The system shall support OAuth 2.0 and related authentication flows. " * 5
    parsed = ParsedDocument(
        filename="req.pdf",
        pages=[PageContent(
            page_number=1,
            text=f"2. Functional Requirements\n\n{long_para}",
            tables=[],
        )],
    )
    chunks = await chunk_document(parsed, "proj_1")
    non_headers = [c for c in chunks if c.detected_type != "header"]
    assert len(non_headers) > 0, "Expected at least one non-header chunk"
    assert all(c.section_hint == "2. Functional Requirements" for c in non_headers)
