"""Tests for GitHub MCP tools and sync service.

httpx calls are intercepted with respx so no real GitHub API hits occur.
"""

import pytest
import respx
from httpx import Response

import app.mcp.github_server as gh_server
from app.schemas.sync import SyncStatus
from app.services.github_sync import sync_epics_to_github

MILESTONE_PAYLOAD = {
    "number": 1,
    "title": "Epic 1",
    "description": "First epic",
    "html_url": "https://github.com/owner/repo/milestone/1",
    "state": "open",
}

ISSUE_PAYLOAD = {
    "number": 10,
    "title": "Task 1",
    "html_url": "https://github.com/owner/repo/issues/10",
    "state": "open",
    "milestone": {"number": 1},
}


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    monkeypatch.setattr(gh_server.settings, "github_token", "test-token")
    monkeypatch.setattr(gh_server.settings, "github_owner", "owner")
    monkeypatch.setattr(gh_server.settings, "github_repo", "repo")


# --- MCP tool unit tests ---

@respx.mock
def test_create_github_milestone():
    respx.post("https://api.github.com/repos/owner/repo/milestones").mock(
        return_value=Response(201, json=MILESTONE_PAYLOAD)
    )
    result = gh_server.create_github_milestone(
        repo="repo",
        title="Epic 1",
        description="First epic",
        due_date="",
    )
    assert result["number"] == 1
    assert result["title"] == "Epic 1"


@respx.mock
def test_create_github_milestone_with_due_date():
    respx.post("https://api.github.com/repos/owner/repo/milestones").mock(
        return_value=Response(201, json=MILESTONE_PAYLOAD)
    )
    result = gh_server.create_github_milestone(
        repo="repo",
        title="Epic 1",
        description="",
        due_date="2026-12-31T00:00:00Z",
    )
    assert result["number"] == 1
    sent = respx.calls.last.request
    import json
    body = json.loads(sent.content)
    assert body["due_on"] == "2026-12-31T00:00:00Z"


@respx.mock
def test_create_github_issue():
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=Response(201, json=ISSUE_PAYLOAD)
    )
    result = gh_server.create_github_issue(
        repo="repo",
        title="Task 1",
        body="Do the thing",
        milestone_number=1,
        labels=["task"],
        assignees=[],
    )
    assert result["number"] == 10
    assert result["milestone"]["number"] == 1


@respx.mock
def test_get_github_repo_issues():
    respx.get("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=Response(200, json=[ISSUE_PAYLOAD])
    )
    issues = gh_server.get_github_repo_issues(repo="repo", milestone=1)
    assert len(issues) == 1
    assert issues[0]["number"] == 10


def test_create_milestone_raises_without_token(monkeypatch):
    monkeypatch.setattr(gh_server.settings, "github_token", "")
    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        gh_server.create_github_milestone("repo", "T", "", "")


@respx.mock
def test_create_milestone_raises_on_http_error():
    respx.post("https://api.github.com/repos/owner/repo/milestones").mock(
        return_value=Response(422, json={"message": "Validation Failed"})
    )
    from httpx import HTTPStatusError
    with pytest.raises(HTTPStatusError):
        gh_server.create_github_milestone("repo", "T", "", "")


# --- Sync service tests ---

@respx.mock
def test_sync_epics_empty_list():
    result = sync_epics_to_github(epics=[])
    assert result == {"synced": 0, "skipped": 0, "failed": 0, "status": SyncStatus.synced}


@respx.mock
def test_sync_one_epic_two_tasks():
    respx.post("https://api.github.com/repos/owner/repo/milestones").mock(
        return_value=Response(201, json=MILESTONE_PAYLOAD)
    )
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=Response(201, json=ISSUE_PAYLOAD)
    )
    epics = [
        {
            "title": "Epic 1",
            "description": "First",
            "due_date": "",
            "tasks": [
                {"title": "Task A", "body": "", "labels": ["task"], "assignees": []},
                {"title": "Task B", "body": "", "labels": ["task"], "assignees": []},
            ],
        }
    ]
    result = sync_epics_to_github(epics=epics)
    # 1 milestone + 2 issues = 3 synced
    assert result["synced"] == 3
    assert result["failed"] == 0
    assert result["status"] == SyncStatus.synced


@respx.mock
def test_sync_milestone_failure_skips_tasks():
    respx.post("https://api.github.com/repos/owner/repo/milestones").mock(
        return_value=Response(500, json={"message": "Server Error"})
    )
    epics = [
        {
            "title": "Bad Epic",
            "description": "",
            "due_date": "",
            "tasks": [{"title": "T1", "body": "", "labels": ["task"], "assignees": []}],
        }
    ]
    result = sync_epics_to_github(epics=epics)
    assert result["failed"] == 1
    assert result["skipped"] == 1
    assert result["synced"] == 0
    assert result["status"] == SyncStatus.failed


@respx.mock
def test_sync_issue_failure_does_not_abort_other_tasks():
    respx.post("https://api.github.com/repos/owner/repo/milestones").mock(
        return_value=Response(201, json=MILESTONE_PAYLOAD)
    )
    # First issue succeeds, second fails
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        side_effect=[
            Response(201, json=ISSUE_PAYLOAD),
            Response(422, json={"message": "Validation Failed"}),
        ]
    )
    epics = [
        {
            "title": "Epic",
            "description": "",
            "due_date": "",
            "tasks": [
                {"title": "T1", "body": "", "labels": ["task"], "assignees": []},
                {"title": "T2", "body": "", "labels": ["task"], "assignees": []},
            ],
        }
    ]
    result = sync_epics_to_github(epics=epics)
    assert result["synced"] == 2   # milestone + 1 issue
    assert result["failed"] == 1
    assert result["status"] == SyncStatus.synced


def test_sync_raises_without_repo(monkeypatch):
    import app.services.github_sync as svc
    monkeypatch.setattr(svc.settings, "github_repo", "")
    with pytest.raises(RuntimeError, match="GITHUB_REPO"):
        sync_epics_to_github(epics=[{"title": "E1", "tasks": []}])
