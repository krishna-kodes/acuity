"""DOCX proposal export."""

import os

from docx import Document as DocxDocument


def generate_proposal_docx(project_id: int, title: str, content: str, output_dir: str = "documents") -> str:
    """Write a DOCX file for the project proposal. Returns the file path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"proposal_{project_id}.docx")
    doc = DocxDocument()
    doc.add_heading(title, level=0)
    for paragraph in content.split("\n\n"):
        if paragraph.strip():
            doc.add_paragraph(paragraph.strip())
    doc.save(path)
    return path
