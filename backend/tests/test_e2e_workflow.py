"""
E2E integration tests — phases 3–6 flow and GitHub sync.

Strategy: mock run_phase() and sync_epics_to_github() to avoid real LLM/GitHub calls.
Focus: router logic, DB persistence, and endpoint response shapes.

Patch targets:
  - run_phase is imported inside each endpoint body via
      `from app.services.workflow import run_phase`
    so patching `app.services.workflow.run_phase` intercepts it at the source.
  - sync_epics_to_github is imported inside sync_to_github via
      `from app.services.github_sync import sync_epics_to_github`
    so patching `app.services.github_sync.sync_epics_to_github` intercepts it.
"""

from unittest.mock import AsyncMock, patch

from app.models.enums import SyncStatus
from app.models.sync import Epic, Task

# ---------------------------------------------------------------------------
# Mock state returned by run_phase
# ---------------------------------------------------------------------------

MOCK_TECH_STACK = {
    "frontend": ["Next.js"],
    "backend": ["FastAPI"],
    "database": ["SQLite"],
    "infra": ["Railway"],
    "rationale": "Best fit for the project scope.",
}

MOCK_TEAM = {
    "members": [
        {
            "id": 1,
            "name": "Alice Chen",
            "seniority": "senior",
            "availability_pct": 80,
            "skills": ["Python", "FastAPI"],
        },
        {
            "id": 2,
            "name": "Bob Kim",
            "seniority": "mid",
            "availability_pct": 100,
            "skills": ["Next.js", "React"],
        },
    ],
    "technologies": ["Next.js", "FastAPI"],
}

MOCK_EFFORT = {
    "total_weeks": 12,
    "total_points": 80,
    "confidence": 0.8,
    "breakdown": {"Phase 1": 20, "Phase 2": 30, "Phase 3": 30},
    "reasoning": "Based on similar historical projects.",
}

MOCK_EPICS = [
    {
        "title": "Authentication",
        "description": "User authentication system",
        "due_date": "2026-09-01",
        "tasks": [
            {
                "title": "Login page",
                "description": "Build login UI",
                "story_points": 3,
                "labels": ["frontend"],
            },
            {
                "title": "JWT middleware",
                "description": "Auth middleware",
                "story_points": 5,
                "labels": ["backend"],
            },
        ],
    },
    {
        "title": "Document Ingestion",
        "description": "PDF/DOCX ingestion pipeline",
        "due_date": "2026-09-15",
        "tasks": [
            {
                "title": "PDF parser",
                "description": "Parse PDFs",
                "story_points": 5,
                "labels": ["backend"],
            },
        ],
    },
]


def make_run_phase_mock(state_override: dict):
    """Return an AsyncMock that resolves to a ProjectState-like dict."""
    base = {
        "project_id": "1",
        "tech_stack": {},
        "team_suggestion": {},
        "effort_estimates": {},
        "epics": [],
        "phase_status": {},
    }
    base.update(state_override)
    return AsyncMock(return_value=base)


# ---------------------------------------------------------------------------
# Phase 3: Tech stack
# ---------------------------------------------------------------------------


class TestPhase3Stack:
    def test_stack_returns_tech_stack_response(self, client, project_id):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"tech_stack": MOCK_TECH_STACK}),
        ):
            resp = client.post(f"/api/v1/projects/{project_id}/stack")

        assert resp.status_code == 200
        data = resp.json()
        assert data["frontend"] == ["Next.js"]
        assert data["backend"] == ["FastAPI"]
        assert "rationale" in data

    def test_stack_persists_to_project(self, client, project_id, db_session):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"tech_stack": MOCK_TECH_STACK}),
        ):
            client.post(f"/api/v1/projects/{project_id}/stack")

        from app.models.project import Project

        project = db_session.query(Project).filter(Project.id == int(project_id)).first()
        db_session.refresh(project)
        assert project.tech_stack is not None
        assert project.tech_stack.get("frontend") == ["Next.js"]


# ---------------------------------------------------------------------------
# Phase 4: Team suggestion
# ---------------------------------------------------------------------------


class TestPhase4Team:
    def test_team_returns_members(self, client, project_id):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"team_suggestion": MOCK_TEAM}),
        ):
            resp = client.post(f"/api/v1/projects/{project_id}/team")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["members"], list)
        assert data["total"] == 2

    def test_team_persists_to_project(self, client, project_id, db_session):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"team_suggestion": MOCK_TEAM}),
        ):
            client.post(f"/api/v1/projects/{project_id}/team")

        from app.models.project import Project

        project = db_session.query(Project).filter(Project.id == int(project_id)).first()
        db_session.refresh(project)
        assert project.team_suggestion is not None
        assert len(project.team_suggestion["members"]) == 2


# ---------------------------------------------------------------------------
# Phase 5: Effort estimation
# ---------------------------------------------------------------------------


class TestPhase5Estimate:
    def test_estimate_returns_total_points_and_weeks(self, client, project_id):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"effort_estimates": MOCK_EFFORT}),
        ):
            resp = client.post(f"/api/v1/projects/{project_id}/estimate")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_points"] == 80
        assert data["total_weeks"] == 12.0

    def test_estimate_persists_to_project(self, client, project_id, db_session):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"effort_estimates": MOCK_EFFORT}),
        ):
            client.post(f"/api/v1/projects/{project_id}/estimate")

        from app.models.project import Project

        project = db_session.query(Project).filter(Project.id == int(project_id)).first()
        db_session.refresh(project)
        assert project.effort_estimates is not None
        assert project.effort_estimates["total_weeks"] == 12


# ---------------------------------------------------------------------------
# Phase 6: Epic generation
# ---------------------------------------------------------------------------


class TestPhase6Epics:
    def test_generate_epics_persists_to_db(self, client, project_id, db_session):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"epics": MOCK_EPICS}),
        ):
            resp = client.post(f"/api/v1/projects/{project_id}/epics")

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

        epics = db_session.query(Epic).filter(Epic.project_id == int(project_id)).all()
        assert len(epics) == 2
        assert epics[0].title == "Authentication"

    def test_generate_epics_creates_tasks_in_db(self, client, project_id, db_session):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"epics": MOCK_EPICS}),
        ):
            client.post(f"/api/v1/projects/{project_id}/epics")

        epics = db_session.query(Epic).filter(Epic.project_id == int(project_id)).all()
        all_tasks = []
        for e in epics:
            tasks = db_session.query(Task).filter(Task.epic_id == e.id).all()
            all_tasks.extend(tasks)

        assert len(all_tasks) == 3  # 2 tasks in epic 1, 1 task in epic 2
        task_titles = {t.title for t in all_tasks}
        assert "Login page" in task_titles
        assert "JWT middleware" in task_titles
        assert "PDF parser" in task_titles

    def test_get_epics_returns_db_rows(self, client, project_id, db_session):
        # First generate epics
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"epics": MOCK_EPICS}),
        ):
            client.post(f"/api/v1/projects/{project_id}/epics")

        # Then GET them
        resp = client.get(f"/api/v1/projects/{project_id}/epics")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["epics"]) == 2
        assert data["epics"][0]["title"] == "Authentication"
        tasks = data["epics"][0]["tasks"]
        assert len(tasks) == 2
        assert tasks[0]["story_points"] in (3, 5)  # matches MOCK_EPICS

    def test_get_epics_includes_sync_status(self, client, project_id, db_session):
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"epics": MOCK_EPICS}),
        ):
            client.post(f"/api/v1/projects/{project_id}/epics")

        resp = client.get(f"/api/v1/projects/{project_id}/epics")
        data = resp.json()
        for epic in data["epics"]:
            assert "sync_status" in epic
            assert epic["sync_status"] == "pending"


# ---------------------------------------------------------------------------
# GitHub sync
# ---------------------------------------------------------------------------


class TestGitHubSync:
    def _seed_epics(self, client, project_id):
        """Helper: generate epics in DB first."""
        with patch(
            "app.services.workflow.run_phase",
            make_run_phase_mock({"epics": MOCK_EPICS}),
        ):
            client.post(f"/api/v1/projects/{project_id}/epics")

    def test_sync_calls_github_with_real_epics(self, client, project_id, db_session):
        self._seed_epics(client, project_id)

        with patch("app.services.github_sync.sync_epics_to_github") as mock_sync:
            mock_sync.return_value = {
                "synced": 5,
                "skipped": 0,
                "failed": 0,
                "status": "synced",
            }
            resp = client.post(f"/api/v1/projects/{project_id}/sync")

        assert resp.status_code == 200
        mock_sync.assert_called_once()
        # Router calls via factory lambda as positional args: (epics, config)
        epics_arg = mock_sync.call_args.args[0]
        assert len(epics_arg) == 2
        assert epics_arg[0]["title"] == "Authentication"
        # Each epic has tasks
        assert len(epics_arg[0]["tasks"]) == 2
        # Task body field (not description)
        assert "body" in epics_arg[0]["tasks"][0]

    def test_sync_returns_correct_counts(self, client, project_id, db_session):
        self._seed_epics(client, project_id)

        with patch("app.services.github_sync.sync_epics_to_github") as mock_sync:
            mock_sync.return_value = {
                "synced": 5,
                "skipped": 0,
                "failed": 0,
                "status": "synced",
            }
            resp = client.post(f"/api/v1/projects/{project_id}/sync")

        assert resp.status_code == 200
        data = resp.json()
        assert data["synced"] == 5
        assert data["failed"] == 0

    def test_sync_updates_sync_status_in_db(self, client, project_id, db_session):
        self._seed_epics(client, project_id)

        with patch("app.services.github_sync.sync_epics_to_github") as mock_sync:
            mock_sync.return_value = {
                "synced": 5,
                "skipped": 0,
                "failed": 0,
                "status": "synced",
            }
            client.post(f"/api/v1/projects/{project_id}/sync")

        epics = db_session.query(Epic).filter(Epic.project_id == int(project_id)).all()
        for epic in epics:
            db_session.refresh(epic)
            assert epic.sync_status == SyncStatus.synced

    def test_sync_empty_epics_returns_zero_counts(self, client, project_id, db_session):
        """If no epics in DB, sync should return zero counts without erroring."""
        with patch("app.services.github_sync.sync_epics_to_github") as mock_sync:
            mock_sync.return_value = {
                "synced": 0,
                "skipped": 0,
                "failed": 0,
                "status": "synced",
            }
            resp = client.post(f"/api/v1/projects/{project_id}/sync")

        assert resp.status_code == 200
        data = resp.json()
        assert data["synced"] == 0
