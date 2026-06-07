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

After sync, each epic dict gains:
  "_milestone_number": int
  "_milestone_url": str
  "_tracker_ref": str         # e.g. "#12"
  "_tracker_url": str

Each task dict gains:
  "_issue_number": int
  "_issue_url": str
  "_tracker_ref": str
  "_tracker_url": str
"""

import logging

from app.config import settings
from app.mcp.github_server import create_github_issue, create_github_milestone
from app.schemas.sync import SyncConfigRequest, SyncStatus

logger = logging.getLogger(__name__)


def sync_epics_to_github(epics: list[dict], config: SyncConfigRequest) -> dict:
    """Sync a list of epics (with nested tasks) to GitHub.

    Returns:
        {"synced": int, "skipped": int, "failed": int, "status": SyncStatus}
    """
    if not epics:
        return {"synced": 0, "skipped": 0, "failed": 0, "status": SyncStatus.synced}

    repo = config.github_repo or settings.github_repo
    if not repo:
        raise RuntimeError("No GitHub repo configured (set GITHUB_REPO or per-project sync_config)")

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
            milestone_url: str = milestone.get("html_url", "")
            epic["_milestone_number"] = milestone_number
            epic["_milestone_url"] = milestone_url
            epic["_tracker_ref"] = f"#{milestone_number}"
            epic["_tracker_url"] = milestone_url
            synced += 1
            logger.info("Milestone created: %s (#%d)", epic["title"], milestone_number)
        except Exception as exc:
            logger.error("Failed to create milestone '%s': %s", epic["title"], exc)
            failed += 1
            skipped += len(epic.get("tasks", []))
            continue

        for task in epic.get("tasks", []):
            try:
                issue = create_github_issue(
                    repo=repo,
                    title=task["title"],
                    body=task.get("body", ""),
                    milestone_number=milestone_number,
                    labels=task.get("labels", ["task"]),
                    assignees=task.get("assignees", []),
                )
                issue_number: int = issue["number"]
                issue_url: str = issue.get("html_url", "")
                task["_issue_number"] = issue_number
                task["_issue_url"] = issue_url
                task["_tracker_ref"] = f"#{issue_number}"
                task["_tracker_url"] = issue_url
                synced += 1
                logger.info("Issue created: %s (#%d)", task["title"], issue_number)
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
