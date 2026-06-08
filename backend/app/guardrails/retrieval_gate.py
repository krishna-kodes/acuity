"""Layer 2 — Retrieval quality gate.

Evaluates retrieved chunks before LLM inference. No LLM calls.
Feature flag: RETRIEVAL_GATE_ENABLED (default true).
"""
from dataclasses import dataclass, field

from app.config import settings
from app.guardrails import log_guardrail


@dataclass
class GateResult:
    status: str  # "pass" | "low_confidence" | "no_results" | "provenance_mismatch"
    message: str | None = None
    chunks: list[dict] = field(default_factory=list)


def evaluate(chunks: list[dict], project_id: str, scores: list[float]) -> GateResult:
    """Evaluate retrieval quality. Returns GateResult — never raises."""
    if not settings.retrieval_gate_enabled:
        return GateResult(status="pass", chunks=chunks)

    if not chunks:
        log_guardrail(project_id, 2, "no_results", None, {"n_chunks": 0})
        return GateResult(
            status="no_results",
            message=(
                "This topic doesn't appear to be covered in your uploaded document. "
                "Please upload documents that contain this information, or ask about "
                "content that's already uploaded."
            ),
        )

    mismatched = [c for c in chunks if str(c.get("project_id", "")) != str(project_id)]
    if mismatched:
        log_guardrail(
            project_id, 2, "provenance_mismatch", None,
            {"mismatched_count": len(mismatched), "total": len(chunks)},
        )
        return GateResult(
            status="provenance_mismatch",
            chunks=chunks,
            message="Retrieved content could not be verified against your document.",
        )

    top_score = max(scores) if scores else 0.0
    if top_score < settings.retrieval_confidence_threshold:
        log_guardrail(
            project_id, 2, "low_confidence", top_score,
            {"top_score": top_score, "threshold": settings.retrieval_confidence_threshold},
        )
        return GateResult(
            status="low_confidence",
            chunks=chunks,
            message=(
                "I couldn't find enough information about this in your document. "
                "Try asking more specifically about what's in the document."
            ),
        )

    return GateResult(status="pass", chunks=chunks)
