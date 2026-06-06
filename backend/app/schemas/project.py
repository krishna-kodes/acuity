from pydantic import BaseModel

_PHASE_ORDER = {
    "redaction": 1,
    "chat": 2,
    "techstack": 3,
    "team": 4,
    "estimation": 5,
    "epics": 6,
    "complete": 7,
}


def phase_to_int(phase: str) -> int:
    return _PHASE_ORDER.get(str(phase), 1)


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
