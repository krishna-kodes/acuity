from __future__ import annotations

from pydantic import BaseModel

from app.schemas.proposal_sections import SectionResponse


class ProposalSectionOut(BaseModel):
    heading: str
    body: str


class ProposalRetryRequest(BaseModel):
    comment: str


class RegenerateSectionRequest(BaseModel):
    additional_context: str = ""


class ProposalResponse(BaseModel):
    id: str
    project_id: str
    content_path: str | None = None
    content: str | None = None
    created_at: str
    sections: list[ProposalSectionOut] = []
    structured_sections: list[SectionResponse] | None = None
    template_version: str | None = None
