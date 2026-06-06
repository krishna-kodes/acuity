from pydantic import BaseModel


class ProposalResponse(BaseModel):
    id: str
    project_id: str
    content_path: str
    created_at: str
