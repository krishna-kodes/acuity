"""Layer 3 — Output groundedness + domain consistency judge.

Verifies LLM response is grounded in retrieved chunks.
Feature flag: GROUNDEDNESS_CHECK_ENABLED (default true).
"""
import time
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.config import settings
from app.guardrails import log_guardrail
from app.services.llm_factory import get_llm
from app.services.metrics_tracker import calc_cost, record_latency, record_quality, record_tokens

# REGRESSION: do not change this prompt without re-running evals/regression_suite.py
_GROUNDEDNESS_PROMPT = (
    "System: You are an evaluation judge. Answer only with a JSON object.\n"
    "User:\n"
    "  Context: {context}\n"
    "  Response: {response}\n"
    "  Question: Is every factual claim in the Response directly supported by the Context?\n"
    "  Score 0-1 where 1 = fully grounded, 0 = contains unsupported claims.\n"
    '  Output: {{"score": float, "reasoning": str, "unsupported_claims": list[str]}}'
)


class _LLMResult(BaseModel):
    score: float
    reasoning: str
    unsupported_claims: list[str] = field(default_factory=list)


@dataclass
class GroundednessResult:
    score: float
    reasoning: str
    unsupported_claims: list[str]
    source: str | None = None  # "general_knowledge" when response could come from outside doc


async def evaluate(response: str, context: str, project_id: str) -> GroundednessResult | None:
    """Run groundedness judge. Returns None if GROUNDEDNESS_CHECK_ENABLED=false."""
    if not settings.groundedness_check_enabled:
        return None

    llm = get_llm(fast=False).with_structured_output(_LLMResult, include_raw=True)
    t0 = time.monotonic()
    raw_result: dict = await llm.with_config({"run_name": "groundedness_judge"}).ainvoke(
        [HumanMessage(content=_GROUNDEDNESS_PROMPT.format(
            context=context, response=response
        ))]
    )
    elapsed_ms = (time.monotonic() - t0) * 1000
    gs: _LLMResult = raw_result["parsed"]

    record_latency(int(project_id), "phase_2", "groundedness_judge_node", elapsed_ms)
    _usage = getattr(raw_result.get("raw"), "usage_metadata", None) or {}
    _inp = int(_usage.get("input_tokens", 0))
    _out = int(_usage.get("output_tokens", 0))
    record_tokens(int(project_id), "phase_2", settings.main_llm_model, _inp, _out, calc_cost(_inp, _out))

    score = float(gs.score) if hasattr(gs, "score") else 0.0
    reasoning = gs.reasoning if hasattr(gs, "reasoning") else ""
    claims = list(gs.unsupported_claims) if hasattr(gs, "unsupported_claims") else []

    record_quality(int(project_id), "phase_2", "groundedness", score, reasoning)

    source = "general_knowledge" if (
        score < settings.groundedness_threshold and claims
    ) else None

    if score < settings.groundedness_threshold:
        log_guardrail(
            project_id, 3, "groundedness_warning", score,
            {"score": score, "unsupported_claims": claims, "reasoning": reasoning},
        )

    return GroundednessResult(
        score=score,
        reasoning=reasoning,
        unsupported_claims=claims,
        source=source,
    )
