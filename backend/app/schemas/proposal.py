from pydantic import BaseModel


class ProposalSectionOut(BaseModel):
    heading: str
    body: str


class ProposalRetryRequest(BaseModel):
    comment: str


class ProposalResponse(BaseModel):
    id: str
    project_id: str
    content_path: str
    created_at: str
    sections: list[ProposalSectionOut] = []
