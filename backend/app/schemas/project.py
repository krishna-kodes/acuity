from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    status: str
    current_phase: int
    created_at: str


class TBDItem(BaseModel):
    id: str
    question: str
    level: int
    resolved: bool


class TechStackResponse(BaseModel):
    frontend: list[str]
    backend: list[str]
    database: list[str]
    infra: list[str]
    rationale: str


class EstimationResponse(BaseModel):
    epics: list[dict]
    total_points: int
    total_weeks: float
