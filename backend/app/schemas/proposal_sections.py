from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel

TEMPLATE_VERSION = "1.0"


class ProposalSectionId(str, Enum):
    overview = "overview"
    problem_statement = "problem_statement"
    goals_and_non_goals = "goals_and_non_goals"
    target_audience = "target_audience"
    key_features = "key_features"
    technical_requirements = "technical_requirements"
    risks_and_mitigations = "risks_and_mitigations"
    success_metrics = "success_metrics"
    timeline_and_milestones = "timeline_and_milestones"
    open_questions = "open_questions"


SECTION_TITLES: dict[ProposalSectionId, str] = {
    ProposalSectionId.overview: "Overview & Purpose",
    ProposalSectionId.problem_statement: "Problem Statement",
    ProposalSectionId.goals_and_non_goals: "Goals & Non-Goals",
    ProposalSectionId.target_audience: "Target Audience & Personas",
    ProposalSectionId.key_features: "Key Features & Scope",
    ProposalSectionId.technical_requirements: "Technical Requirements",
    ProposalSectionId.risks_and_mitigations: "Risks & Mitigations",
    ProposalSectionId.success_metrics: "Success Metrics",
    ProposalSectionId.timeline_and_milestones: "Timeline & Milestones",
    ProposalSectionId.open_questions: "Open Questions",
}

# Schema hints passed to LLM per section
SECTION_SCHEMA_HINTS: dict[ProposalSectionId, str] = {
    ProposalSectionId.overview: "2-4 paragraphs of markdown prose summarising purpose and value",
    ProposalSectionId.problem_statement: "2-3 paragraphs describing the problem, its impact, and who it affects",
    ProposalSectionId.goals_and_non_goals: "Markdown with two sub-sections: '### Goals' (bullet list) and '### Non-Goals' (bullet list)",
    ProposalSectionId.target_audience: 'JSON array of persona objects: [{"name":"...","role":"...","needs":"..."}, ...]',
    ProposalSectionId.key_features: 'JSON array of feature objects: [{"title":"...","description":"...","in_scope":true/false}, ...]',
    ProposalSectionId.technical_requirements: "Markdown bullet list of technical constraints, stack choices, and non-functional requirements",
    ProposalSectionId.risks_and_mitigations: 'JSON array of risk objects: [{"risk":"...","mitigation":"..."}, ...]',
    ProposalSectionId.success_metrics: "Markdown bullet list of measurable success criteria (KPIs, acceptance thresholds)",
    ProposalSectionId.timeline_and_milestones: "Markdown table or bullet list of phases/milestones with estimated durations",
    ProposalSectionId.open_questions: "Bullet list of unresolved questions",
}

# Sections where the LLM should return a JSON array (parsed into items field)
TYPED_SECTIONS = {
    ProposalSectionId.target_audience,
    ProposalSectionId.key_features,
    ProposalSectionId.risks_and_mitigations,
}


class SectionStatus(str, Enum):
    generated = "generated"
    draft = "draft"
    failed = "failed"


class RiskItem(BaseModel):
    risk: str
    mitigation: str


class PersonaItem(BaseModel):
    name: str
    role: str
    needs: str


class FeatureItem(BaseModel):
    title: str
    description: str
    in_scope: bool


class SectionResponse(BaseModel):
    section_id: ProposalSectionId
    title: str
    status: SectionStatus
    generated_at: datetime
    content: str
    items: list[dict[str, Any]] | None = None
