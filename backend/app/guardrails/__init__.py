"""Guardrail pipeline for Phase 2 RAG chat.

Layer 1 — domain_classifier: rejects non-PM queries before retrieval
Layer 2 — retrieval_gate:    blocks low-quality retrieval before LLM inference
Layer 3 — groundedness:      warns on ungrounded responses after LLM generation
"""
import json

from app.database import SessionLocal
from app.models.guardrail import GuardrailLog


def log_guardrail(
    project_id: str,
    layer: int,
    trigger: str,
    score: float | None,
    detail: dict,
) -> None:
    """Write a guardrail event to the guardrail_logs table. Never raises."""
    db = SessionLocal()
    try:
        db.add(GuardrailLog(
            project_id=project_id,
            phase="phase_2",
            layer=layer,
            trigger=trigger,
            score=score,
            detail=json.dumps(detail),
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
