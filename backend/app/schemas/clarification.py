from pydantic import BaseModel


class ClarificationCreate(BaseModel):
    tbd_id: str
    action: str
    answer: str | None = None


class ClarificationResponse(BaseModel):
    id: str
    tbd_id: str
    action: str
    answer: str | None
