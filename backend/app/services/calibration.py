"""Estimation feedback loop — turn realized actuals into a calibration factor.

Once a project's epics close on the tracker, `record_outcomes` writes one
`estimation_outcomes` row per epic (estimated vs actual points). `get_calibration`
aggregates those rows into a multiplier that nudges future estimates toward what
the team actually delivers.

Cold start: with fewer than MIN_SAMPLES matching rows the factor is 1.0 (no-op),
so early projects are never distorted by a thin corpus.
"""

import logging

from sqlalchemy.orm import Session

from app.models.enums import SyncStatus
from app.models.project import Project
from app.models.reference import EstimationOutcome
from app.models.sync import Epic

logger = logging.getLogger(__name__)

MIN_SAMPLES = 3
# Clamp the factor so one wild outlier can't 3x an estimate.
_FACTOR_MIN = 0.5
_FACTOR_MAX = 2.0


def _dominant_category(epic: Epic) -> str | None:
    """Most common task label on an epic — the calibration bucket key."""
    counts: dict[str, int] = {}
    for task in epic.tasks:
        if not task.labels:
            continue
        import json
        try:
            labels = json.loads(task.labels)
        except (json.JSONDecodeError, TypeError):
            labels = []
        for lbl in labels:
            counts[lbl] = counts.get(lbl, 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def record_outcomes(project: Project, db: Session) -> int:
    """Write estimation_outcomes for a project whose epics are closed.

    Idempotent per (project_id, epic_id): re-running does not duplicate rows.
    Returns the number of new rows written.
    """
    epics = db.query(Epic).filter(Epic.project_id == project.id).all()
    closed_epics = [e for e in epics if e.remote_state == "closed"]
    if not closed_epics:
        return 0

    existing = {
        o.epic_id
        for o in db.query(EstimationOutcome).filter(EstimationOutcome.project_id == project.id).all()
    }

    written = 0
    for epic in closed_epics:
        if epic.id in existing:
            continue
        if not epic.estimated_points or epic.actual_points is None:
            continue
        db.add(EstimationOutcome(
            project_id=project.id,
            epic_id=epic.id,
            domain=project.domain,
            category=_dominant_category(epic),
            estimated_points=epic.estimated_points,
            actual_points=epic.actual_points,
        ))
        written += 1

    if written:
        db.commit()
        logger.info("Recorded %d estimation outcome(s) for project %s", written, project.id)
    return written


def get_calibration(db: Session, domain: str | None = None, category: str | None = None) -> dict:
    """Return calibration for the given bucket.

    Resolution: try (domain+category) → (category) → (domain) → global.
    The first bucket with >= MIN_SAMPLES wins; otherwise factor 1.0.

    Returns {"factor": float, "samples": int, "bucket": str}.
    """
    rows = db.query(EstimationOutcome).filter(
        EstimationOutcome.estimated_points.isnot(None),
        EstimationOutcome.estimated_points > 0,
        EstimationOutcome.actual_points.isnot(None),
    ).all()

    def _factor(subset: list[EstimationOutcome]) -> float:
        ratios = [o.actual_points / o.estimated_points for o in subset]
        return sum(ratios) / len(ratios)

    buckets: list[tuple[str, list[EstimationOutcome]]] = []
    if domain and category:
        buckets.append((f"{domain}/{category}",
                        [o for o in rows if o.domain == domain and o.category == category]))
    if category:
        buckets.append((f"category:{category}", [o for o in rows if o.category == category]))
    if domain:
        buckets.append((f"domain:{domain}", [o for o in rows if o.domain == domain]))
    buckets.append(("global", rows))

    for name, subset in buckets:
        if len(subset) >= MIN_SAMPLES:
            factor = max(_FACTOR_MIN, min(_FACTOR_MAX, _factor(subset)))
            return {"factor": round(factor, 3), "samples": len(subset), "bucket": name}

    return {"factor": 1.0, "samples": len(rows), "bucket": "cold_start"}


def accuracy_summary(db: Session, project_id: int | None = None) -> dict:
    """Estimated-vs-actual rollup for the metrics dashboard.

    If project_id is given and that project has actuals, summarize its own epics;
    otherwise summarize the whole outcomes corpus.
    """
    per_epic: list[dict] = []
    est_total = 0
    act_total = 0
    abs_err_total = 0.0
    n = 0

    if project_id is not None:
        epics = db.query(Epic).filter(
            Epic.project_id == project_id,
            Epic.actual_points.isnot(None),
        ).all()
        for e in epics:
            if not e.estimated_points:
                continue
            est = e.estimated_points
            act = e.actual_points or 0
            per_epic.append({"epic": e.title, "estimated": est, "actual": act})
            est_total += est
            act_total += act
            abs_err_total += abs(act - est) / est
            n += 1

    # Corpus-wide calibration (always useful context)
    cal = get_calibration(db)

    bias_pct = round(((act_total - est_total) / est_total) * 100, 1) if est_total else None
    mae_pct = round((abs_err_total / n) * 100, 1) if n else None

    return {
        "per_epic": per_epic,
        "estimated_total": est_total,
        "actual_total": act_total,
        "bias_pct": bias_pct,        # +ve = under-estimated (actual > estimate)
        "mae_pct": mae_pct,          # mean absolute % error
        "calibration_factor": cal["factor"],
        "calibration_samples": cal["samples"],
        "calibration_bucket": cal["bucket"],
    }
