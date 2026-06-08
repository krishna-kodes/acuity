"""DOCX proposal export."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from docx import Document as DocxDocument


@dataclass
class ProposalSection:
    heading: str
    body: str


@dataclass
class ProposalContent:
    title: str
    sections: list[ProposalSection] = field(default_factory=list)


def generate_proposal_docx(
    project_id: int,
    content: ProposalContent,
    structured_sections: list[dict[str, Any]] | None = None,
    output_dir: str = "documents",
) -> str:
    """Write a structured DOCX proposal. Returns the file path.

    When structured_sections is provided, renders them in ProposalSectionId enum
    order with typed tables for risks, personas, and features. Falls back to the
    legacy ProposalContent path when structured_sections is None.
    """
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"proposal_{project_id}.docx")
    doc = DocxDocument()
    doc.add_heading(content.title, level=0)

    if structured_sections:
        from app.schemas.proposal_sections import ProposalSectionId

        sec_map = {s["section_id"]: s for s in structured_sections}
        for sid in ProposalSectionId:
            sec = sec_map.get(sid.value)
            if not sec:
                continue
            doc.add_heading(sec["title"], level=1)
            items = sec.get("items") or []
            if items and sid.value == "risks_and_mitigations":
                table = doc.add_table(rows=1, cols=2)
                table.style = "Table Grid"
                hdr = table.rows[0].cells
                hdr[0].text = "Risk"
                hdr[1].text = "Mitigation"
                for item in items:
                    row = table.add_row()
                    row.cells[0].text = str(item.get("risk", ""))
                    row.cells[1].text = str(item.get("mitigation", ""))
            elif items and sid.value == "target_audience":
                table = doc.add_table(rows=1, cols=3)
                table.style = "Table Grid"
                hdr = table.rows[0].cells
                hdr[0].text = "Name"
                hdr[1].text = "Role"
                hdr[2].text = "Needs"
                for item in items:
                    row = table.add_row()
                    row.cells[0].text = str(item.get("name", ""))
                    row.cells[1].text = str(item.get("role", ""))
                    row.cells[2].text = str(item.get("needs", ""))
            elif items and sid.value == "key_features":
                table = doc.add_table(rows=1, cols=3)
                table.style = "Table Grid"
                hdr = table.rows[0].cells
                hdr[0].text = "Scope"
                hdr[1].text = "Feature"
                hdr[2].text = "Description"
                for item in items:
                    row = table.add_row()
                    row.cells[0].text = "In" if item.get("in_scope") else "Out"
                    row.cells[1].text = str(item.get("title", ""))
                    row.cells[2].text = str(item.get("description", ""))
            else:
                body = sec.get("content", "")
                for para in body.split("\n\n"):
                    if para.strip():
                        doc.add_paragraph(para.strip())
    else:
        for section in content.sections:
            doc.add_heading(section.heading, level=1)
            for para in section.body.split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())

    doc.save(path)
    return path
