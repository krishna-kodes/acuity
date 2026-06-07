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


_WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


async def parse_docx(path: str) -> ParsedDocument:
    doc = DocxDocument(path)
    text_lines: list[str] = []
    tables: list[list[list[str]]] = []

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]
        if tag == "p":
            # CT_P/CT_R override .text to return all inner text, causing 3× duplication.
            # Only collect w:t leaf nodes which hold the actual string values.
            text = "".join(n.text or "" for n in block.iter(f"{{{_WNS}}}t"))
            if text.strip():
                text_lines.append(text.strip())
        elif tag == "tbl":
            rows = []
            for row in block.iter(f"{{{_WNS}}}tr"):
                cells = [
                    "".join(n.text or "" for n in cell.iter(f"{{{_WNS}}}t"))
                    for cell in row.iter(f"{{{_WNS}}}tc")
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
