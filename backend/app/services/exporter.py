"""DOCX proposal export."""

import os
from dataclasses import dataclass, field

from docx import Document as DocxDocument


@dataclass
class ProposalSection:
    heading: str
    body: str


@dataclass
class ProposalContent:
    title: str
    sections: list[ProposalSection] = field(default_factory=list)


def generate_proposal_docx(project_id: int, content: ProposalContent, output_dir: str = "documents") -> str:
    """Write a structured DOCX proposal. Returns the file path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"proposal_{project_id}.docx")
    doc = DocxDocument()
    doc.add_heading(content.title, level=0)
    for section in content.sections:
        doc.add_heading(section.heading, level=1)
        for para in section.body.split("\n\n"):
            if para.strip():
                doc.add_paragraph(para.strip())
    doc.save(path)
    return path
