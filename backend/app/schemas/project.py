from pydantic import BaseModel, Field

_PHASE_ORDER = {
    "redaction": 1,
    "chat": 2,
    "modules": 3,
    "techstack": 4,
    "team": 5,
    "estimation": 6,
    "epics": 7,
    "complete": 8,
}


def phase_to_int(phase: str) -> int:
    return _PHASE_ORDER.get(str(phase), 1)


class ProjectCreate(BaseModel):
    name: str
    domain: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    domain: str | None
    status: str
    current_phase: int
    created_at: str
    updated_at: str
    module_count: int = 0
    tech_preview: list[str] = []
    total_weeks: float | None = None
    team_size: int = 0
    milestones_url: str | None = None
    document_filename: str | None = None


class ProjectDetailResponse(BaseModel):
    id: str
    name: str
    domain: str | None
    status: str
    current_phase: int
    created_at: str
    summary: str | None = None


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


class ChatRequest(BaseModel):
    message: str
    proceed: bool = False


class TaskOutput(BaseModel):
    title: str
    description: str
    story_points: int = Field(ge=1, le=13, default=3)
    labels: list[str] = Field(default_factory=list)


class EpicOutput(BaseModel):
    title: str
    description: str
    due_date: str  # "YYYY-MM-DD"
    tasks: list[TaskOutput] = Field(default_factory=list)


class EpicsOutput(BaseModel):
    epics: list[EpicOutput] = Field(min_length=1, max_length=10)


class TeamResponse(BaseModel):
    members: list[dict]
    total: int


class TeamUpdateRequest(BaseModel):
    members: list[dict]
