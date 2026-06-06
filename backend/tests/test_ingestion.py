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
