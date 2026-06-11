"""Metrics instrumentation helpers — thin wrappers around SessionLocal writes."""

import time
import traceback as tb
from collections.abc import Generator
from contextlib import contextmanager

from app.config import settings


def calc_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * settings.cost_per_1k_input_tokens / 1000
        + output_tokens * settings.cost_per_1k_output_tokens / 1000
    )


def record_tokens(
    project_id: int,
    phase: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
) -> None:
    if not settings.metrics_enabled:
        return
    from app.database import SessionLocal
    from app.models.observability import Metric

    db = SessionLocal()
    try:
        db.add(Metric(
            project_id=project_id,
            phase=phase,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_latency(
    project_id: int,
    phase: str,
    node_name: str,
    duration_ms: float,
) -> None:
    if not settings.metrics_enabled:
        return
    from app.database import SessionLocal
    from app.models.observability import LatencyLog

    db = SessionLocal()
    try:
        db.add(LatencyLog(
            project_id=project_id,
            phase=phase,
            node_name=node_name,
            duration_ms=duration_ms,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_error(
    project_id: int,
    phase: str,
    error_type: str,
    message: str,
    traceback: str | None = None,
) -> None:
    if not settings.metrics_enabled:
        return
    from app.database import SessionLocal
    from app.models.observability import ErrorLog

    db = SessionLocal()
    try:
        db.add(ErrorLog(
            project_id=project_id,
            phase=phase,
            error_type=error_type,
            message=message,
            traceback=traceback,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_quality(
    project_id: int,
    phase: str,
    score_type: str,
    score: float,
    reasoning: str | None = None,
) -> None:
    if not settings.metrics_enabled:
        return
    from app.database import SessionLocal
    from app.models.observability import QualityLog

    db = SessionLocal()
    try:
        db.add(QualityLog(
            project_id=project_id,
            phase=phase,
            score_type=score_type,
            score=score,
            reasoning=reasoning,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def record_retrieval(
    project_id: int,
    phase: str,
    query_index: int,
    n_retrieved: int,
    n_reranked: int,
    top_score: float,
    avg_score: float,
) -> None:
    if not settings.metrics_enabled:
        return
    from app.database import SessionLocal
    from app.models.observability import RetrievalLog

    db = SessionLocal()
    try:
        db.add(RetrievalLog(
            project_id=project_id,
            phase=phase,
            query_index=query_index,
            n_retrieved=n_retrieved,
            n_reranked=n_reranked,
            top_score=top_score,
            avg_score=avg_score,
        ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@contextmanager
def timed_node(
    project_id: int,
    phase: str,
    node_name: str,
) -> Generator[None, None, None]:
    start = time.monotonic()
    try:
        yield
    except Exception as exc:
        record_error(
            project_id,
            phase,
            type(exc).__name__,
            str(exc),
            tb.format_exc(),
        )
        raise
    finally:
        record_latency(project_id, phase, node_name, (time.monotonic() - start) * 1000)
