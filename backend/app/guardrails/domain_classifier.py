"""Layer 1 — Input domain classification.

Rejects non-PM queries before retrieval. Uses the fast LLM via the factory.
Feature flag: DOMAIN_CLASSIFIER_ENABLED (default true).
"""
import time

from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.config import settings
from app.guardrails import log_guardrail
from app.services.llm_factory import get_llm
from app.services.metrics_tracker import calc_cost, record_latency, record_tokens

_PROMPT = (
    "You are a domain classifier for a project management tool. "
    "Classify the user query and return ONLY a JSON object with these exact fields:\n"
    '  "domain": short label (e.g. "cooking", "project_management", "weather", "coding")\n'
    '  "is_pm_related": true if the query is about software project management, requirements '
    "documents, team composition, tech stacks, epics, timelines, sprints, effort estimation, "
    "document analysis, or product requirements. False otherwise.\n"
    '  "confidence": float 0-1, your certainty in this classification\n\n'
    "Query: {query}"
)


class _ClassifierResult(BaseModel):
    domain: str
    is_pm_related: bool
    confidence: float


async def classify(query: str, project_id: str) -> None:
    """Raise HTTP 400 if query is clearly non-PM-domain with high confidence.

    No-op when DOMAIN_CLASSIFIER_ENABLED=false.
    """
    if not settings.domain_classifier_enabled:
        return

    llm = get_llm(fast=True).with_structured_output(_ClassifierResult)
    t0 = time.monotonic()
    result: _ClassifierResult = await llm.with_config(
        {"run_name": "domain_classifier"}
    ).ainvoke([HumanMessage(content=_PROMPT.format(query=query))])
    elapsed_ms = (time.monotonic() - t0) * 1000

    record_latency(int(project_id), "phase_2", "domain_classifier_node", elapsed_ms)
    record_tokens(
        int(project_id), "phase_2", settings.fast_llm_model,
        150, 50, calc_cost(150, 50),
    )

    if (
        not result.is_pm_related
        and result.confidence >= settings.domain_classifier_confidence_threshold
    ):
        log_guardrail(
            project_id, 1, "domain_rejected",
            result.confidence, result.model_dump(),
        )
        raise HTTPException(
            status_code=400,
            detail=(
                f"This system only answers questions about project management. "
                f"Your question appears to be about {result.domain}."
            ),
        )
