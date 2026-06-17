"""Bidirectional sync — pull GitHub issue/milestone state back into the DB.

Write-path (github_sync.py) pushes epics→milestones, tasks→issues and stores the
remote numbers. This module reads that remote state back: issue open/closed,
closed_at, and a realized `actual_points` value. Populating actuals is what
unlocks the estimation feedback loop (calibration.py).

GitHub has no native story-point field, so actual_points is resolved per task in
this documented order:
  1. issue label `actual-points:N`   (dev sets the realized value on close)
  2. issue label `points:N`          (planning estimate carried on the issue)
  3. fallback: task.estimated_points if the issue is closed, else 0 (still open)

The pull is idempotent: it keys on the persisted github_issue_number /
github_milestone_number, so re-running converges to the same DB state.
"""

import logging
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.mcp.github_server import get_github_repo_issues, get_milestone
from app.models.enums import SyncStatus
from app.models.project import Project
from app.models.sync import Epic, Task

logger = logging.getLogger(__name__)

_POINTS_LABEL_RE = re.compile(r"^(?:actual-points|points)\s*[:=]\s*(\d+)$", re.IGNORECASE)
_ACTUAL_LABEL_RE = re.compile(r"^actual-points\s*[:=]\s*(\d+)$", re.IGNORECASE)


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, AttributeError):
        return None


def _label_names(issue: dict) -> list[str]:
    out: list[str] = []
    for lbl in issue.get("labels", []) or []:
        if isinstance(lbl, dict):
            name = lbl.get("name")
        else:
            name = lbl
        if name:
            out.append(str(name))
    return out


def resolve_actual_points(issue: dict, estimated: int | None) -> int:
    """Resolve realized story points for a GitHub issue per the documented contract."""
    labels = _label_names(issue)

    # Tier 1: actual-points:N wins outright
    for name in labels:
        m = _ACTUAL_LABEL_RE.match(name.strip())
        if m:
            return int(m.group(1))

    # Tier 2: points:N (also matches actual-points handled above, harmless)
    for name in labels:
        m = _POINTS_LABEL_RE.match(name.strip())
        if m:
            return int(m.group(1))

    # Tier 3: closed issue delivered its estimate; open issue contributes nothing yet
    if issue.get("state") == "closed":
        return estimated or 0
    return 0


def pull_sync_state(project: Project, db: Session) -> dict:
    """Refresh epics/tasks of a project from their GitHub remotes.

    Returns counts: {"updated", "closed", "still_open", "skipped_unsynced"}.
    """
    repo = None
    if project.sync_config:
        repo = project.sync_config.get("github_repo")
    repo = repo or settings.github_repo
    if not repo:
        raise RuntimeError("No GitHub repo configured (set GITHUB_REPO or per-project sync_config)")

    epics = db.query(Epic).filter(Epic.project_id == project.id).all()

    updated = 0
    closed = 0
    still_open = 0
    skipped = 0

    for epic in epics:
        if not epic.github_milestone_number:
            skipped += 1
            continue

        try:
            issues = get_github_repo_issues(repo, epic.github_milestone_number)
        except Exception as exc:
            logger.warning("Pull: could not list issues for milestone #%s: %s",
                           epic.github_milestone_number, exc)
            continue

        # GitHub issues endpoint also returns PRs; keep real issues only
        by_number = {i["number"]: i for i in issues if "pull_request" not in i}

        epic_actual = 0
        for task in epic.tasks:
            if not task.github_issue_number:
                continue
            issue = by_number.get(task.github_issue_number)
            if issue is None:
                continue
            state = issue.get("state", "open")
            task.remote_state = state
            task.closed_at = _parse_iso(issue.get("closed_at"))
            task.actual_points = resolve_actual_points(issue, task.estimated_points)
            epic_actual += task.actual_points or 0
            if state == "closed":
                closed += 1
            else:
                still_open += 1
            updated += 1

        # Roll up the milestone state onto the epic
        try:
            ms = get_milestone(repo, epic.github_milestone_number)
            epic.remote_state = ms.get("state", "open")
            epic.closed_at = _parse_iso(ms.get("closed_at"))
        except Exception as exc:
            logger.warning("Pull: could not read milestone #%s: %s",
                           epic.github_milestone_number, exc)
            # Fall back to deriving epic state from its tasks
            task_states = [t.remote_state for t in epic.tasks if t.github_issue_number]
            if task_states and all(s == "closed" for s in task_states):
                epic.remote_state = "closed"

        epic.actual_points = epic_actual
        if epic.sync_status == SyncStatus.pending:
            epic.sync_status = SyncStatus.synced

    db.commit()

    return {"updated": updated, "closed": closed, "still_open": still_open, "skipped_unsynced": skipped}
