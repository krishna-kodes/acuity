"""GitHub MCP server — exposes milestone and issue tools for the LangGraph Phase 6 agent."""

import httpx
from fastmcp import FastMCP

from app.config import settings

mcp = FastMCP("acuity-github")

_GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    if not settings.github_token:
        raise RuntimeError("GITHUB_TOKEN not configured")
    return {
        "Authorization": f"Bearer {settings.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@mcp.tool
def create_github_milestone(
    repo: str,
    title: str,
    description: str,
    due_date: str,
) -> dict:
    """Create a GitHub Milestone (maps to an Epic)."""
    url = f"{_GITHUB_API}/repos/{settings.github_owner}/{repo}/milestones"
    payload: dict = {"title": title, "description": description}
    if due_date:
        payload["due_on"] = due_date
    with httpx.Client() as client:
        resp = client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@mcp.tool
def create_github_issue(
    repo: str,
    title: str,
    body: str,
    milestone_number: int,
    labels: list[str],
    assignees: list[str],
) -> dict:
    """Create a GitHub Issue (maps to a Story or Task)."""
    url = f"{_GITHUB_API}/repos/{settings.github_owner}/{repo}/issues"
    payload = {
        "title": title,
        "body": body,
        "milestone": milestone_number,
        "labels": labels,
        "assignees": assignees,
    }
    with httpx.Client() as client:
        resp = client.post(url, json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@mcp.tool
def list_github_milestones(repo: str) -> list[dict]:
    """List all milestones (open + closed) for a repo."""
    url = f"{_GITHUB_API}/repos/{settings.github_owner}/{repo}/milestones"
    params = {"state": "all", "per_page": "100"}
    with httpx.Client() as client:
        resp = client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return [{"number": m["number"], "title": m["title"], "html_url": m.get("html_url", "")} for m in resp.json()]


@mcp.tool
def get_github_repo_issues(repo: str, milestone: int) -> list[dict]:
    """List all GitHub Issues for a milestone (used to verify sync)."""
    url = f"{_GITHUB_API}/repos/{settings.github_owner}/{repo}/issues"
    params = {"milestone": str(milestone), "state": "all", "per_page": "100"}
    with httpx.Client() as client:
        resp = client.get(url, params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json()


@mcp.tool
def get_milestone(repo: str, number: int) -> dict:
    """Read a single milestone's current state (used by bidirectional pull).

    Returns state ('open'|'closed'), open/closed issue counts, due/closed timestamps.
    """
    url = f"{_GITHUB_API}/repos/{settings.github_owner}/{repo}/milestones/{number}"
    with httpx.Client() as client:
        resp = client.get(url, headers=_headers())
        resp.raise_for_status()
        m = resp.json()
    return {
        "number": m["number"],
        "title": m["title"],
        "state": m.get("state", "open"),
        "open_issues": m.get("open_issues", 0),
        "closed_issues": m.get("closed_issues", 0),
        "due_on": m.get("due_on"),
        "closed_at": m.get("closed_at"),
        "html_url": m.get("html_url", ""),
    }
