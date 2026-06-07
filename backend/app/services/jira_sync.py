"""Orchestrates syncing epics/tasks to Jira via the mcp-atlassian MCP server.

Epics  → Jira issue type 'Epic'
Tasks  → Jira issue type 'Story' with parent set to the epic's issue key

Expected epic dict shape (same as github_sync):
  {
    "title": str,
    "description": str,
    "tasks": [{"title": str, "body": str, "labels": list[str], "assignees": list[str]}]
  }
"""

import logging

from app.config import settings
from app.mcp.jira_server import call_jira_tool
from app.schemas.sync import SyncConfigRequest, SyncStatus

logger = logging.getLogger(__name__)


async def sync_epics_to_jira(epics: list[dict], config: SyncConfigRequest) -> dict:
    """Sync epics (with nested tasks) to Jira.

    Returns:
        {"synced": int, "skipped": int, "failed": int, "status": SyncStatus}
    """
    if not epics:
        return {"synced": 0, "skipped": 0, "failed": 0, "status": SyncStatus.synced}

    project_key = config.jira_project_key or settings.jira_project_key
    if not project_key:
        raise RuntimeError("No Jira project key configured (set JIRA_PROJECT_KEY or per-project sync_config)")

    synced = 0
    skipped = 0
    failed = 0

    for epic in epics:
        try:
            epic_result = await call_jira_tool(
                "jira_create_issue",
                {
                    "project_key": project_key,
                    "summary": epic["title"],
                    "issue_type": "Epic",
                    "description": epic.get("description", ""),
                },
            )
            # mcp-atlassian returns a list of TextContent; extract the issue key from text
            epic_key = _extract_issue_key(epic_result)
            epic["_jira_key"] = epic_key
            epic["_jira_url"] = _build_issue_url(epic_key)
            synced += 1
            logger.info("Jira Epic created: %s (%s)", epic["title"], epic_key)
        except Exception as exc:
            logger.error("Failed to create Jira Epic '%s': %s", epic["title"], exc)
            failed += 1
            skipped += len(epic.get("tasks", []))
            continue

        for task in epic.get("tasks", []):
            try:
                task_result = await call_jira_tool(
                    "jira_create_issue",
                    {
                        "project_key": project_key,
                        "summary": task["title"],
                        "issue_type": "Story",
                        "description": task.get("body", ""),
                        "additional_fields": {"parent": {"key": epic_key}},
                    },
                )
                task_key = _extract_issue_key(task_result)
                task["_jira_key"] = task_key
                task["_jira_url"] = _build_issue_url(task_key)
                synced += 1
                logger.info("Jira Story created: %s (%s)", task["title"], task_key)
            except Exception as exc:
                logger.error("Failed to create Jira Story '%s': %s", task["title"], exc)
                failed += 1

    if failed == 0:
        status = SyncStatus.synced
    elif synced == 0:
        status = SyncStatus.failed
    else:
        status = SyncStatus.synced

    return {"synced": synced, "skipped": skipped, "failed": failed, "status": status}


def _extract_issue_key(content: list) -> str:
    """Pull the Jira issue key (e.g. 'PROJ-1') from mcp-atlassian TextContent list."""
    import re
    for item in content:
        text = getattr(item, "text", "") or str(item)
        match = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", text)
        if match:
            return match.group(1)
    raise ValueError(f"Could not find issue key in mcp-atlassian response: {content}")


def _build_issue_url(issue_key: str) -> str:
    from app.config import settings as _settings
    base = _settings.jira_url.rstrip("/")
    return f"{base}/browse/{issue_key}"
