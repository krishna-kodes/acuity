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
    '  "is_pm_related": true if the query fits ANY of these categories:\n'
    "    - Software project management, requirements documents, epics, sprints, timelines, effort estimation\n"
    "    - Team composition, tech stacks, product requirements\n"
    "    - Asking to explain, describe, elaborate on, or clarify a feature, requirement, or section "
    "from an uploaded document (even if the feature topic is from another domain like healthcare, "
    "finance, or IoT — the user is asking about their requirements, not asking for domain expertise)\n"
    "    - Phrases like 'explain this', 'what does this mean', 'describe this feature', "
    "'tell me more about [requirement]' are always PM-related\n"
    "  False only for clearly unrelated queries like recipes, weather, general trivia, "
    "personal advice, or coding help unrelated to the project.\n"
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

    llm = get_llm(fast=True).with_structured_output(_ClassifierResult, include_raw=True)
    t0 = time.monotonic()
    raw_result: dict = await llm.with_config(
        {"run_name": "domain_classifier"}
    ).ainvoke([HumanMessage(content=_PROMPT.format(query=query))])
    elapsed_ms = (time.monotonic() - t0) * 1000
    result: _ClassifierResult = raw_result["parsed"]

    record_latency(int(project_id), "phase_2", "domain_classifier_node", elapsed_ms)
    _usage = getattr(raw_result.get("raw"), "usage_metadata", None) or {}
    _inp = int(_usage.get("input_tokens", 0))
    _out = int(_usage.get("output_tokens", 0))
    record_tokens(int(project_id), "phase_2", settings.fast_llm_model, _inp, _out, calc_cost(_inp, _out))

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
