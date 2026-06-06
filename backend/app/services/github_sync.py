"""Orchestrates syncing epics/tasks to GitHub using the MCP tools.

Epics  → GitHub Milestones
Tasks  → GitHub Issues with 'task' label + milestone reference

Expected epic dict shape:
  {
    "title": str,
    "description": str,
    "due_date": str,          # ISO 8601, empty string if none
    "tasks": [
      {"title": str, "body": str, "labels": list[str], "assignees": list[str]}
    ]
  }

Returns counts for the SyncResponse schema.
Once E5-T1 (DB schema) is complete, callers should build this list from
the epics/tasks tables rather than passing it in directly.
"""

import logging

from app.config import settings
from app.mcp.github_server import create_github_issue, create_github_milestone
from app.schemas.sync import SyncStatus

logger = logging.getLogger(__name__)


def sync_epics_to_github(epics: list[dict]) -> dict:
    """Sync a list of epics (with nested tasks) to GitHub.

    Returns:
        {"synced": int, "skipped": int, "failed": int, "status": SyncStatus}
    """
    if not epics:
        return {"synced": 0, "skipped": 0, "failed": 0, "status": SyncStatus.synced}

    if not settings.github_repo:
        raise RuntimeError("GITHUB_REPO not configured")

    repo = settings.github_repo
    synced = 0
    skipped = 0
    failed = 0

    for epic in epics:
        try:
            milestone = create_github_milestone(
                repo=repo,
                title=epic["title"],
                description=epic.get("description", ""),
                due_date=epic.get("due_date", ""),
            )
            milestone_number: int = milestone["number"]
            synced += 1
            logger.info("Milestone created: %s (#%d)", epic["title"], milestone_number)
        except Exception as exc:
            logger.error("Failed to create milestone '%s': %s", epic["title"], exc)
            failed += 1
            skipped += len(epic.get("tasks", []))
            continue

        for task in epic.get("tasks", []):
            try:
                create_github_issue(
                    repo=repo,
                    title=task["title"],
                    body=task.get("body", ""),
                    milestone_number=milestone_number,
                    labels=task.get("labels", ["task"]),
                    assignees=task.get("assignees", []),
                )
                synced += 1
                logger.info("Issue created: %s", task["title"])
            except Exception as exc:
                logger.error("Failed to create issue '%s': %s", task["title"], exc)
                failed += 1

    if failed == 0:
        status = SyncStatus.synced
    elif synced == 0:
        status = SyncStatus.failed
    else:
        status = SyncStatus.synced

    return {"synced": synced, "skipped": skipped, "failed": failed, "status": status}
