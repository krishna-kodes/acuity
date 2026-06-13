"""Tests for bidirectional GitHub sync (#1) + estimation feedback loop (#2).

Covers the three graders called out in the plan:
  - actual_points resolution contract (3 tiers)
  - pull_sync_state idempotency (run twice -> identical DB state)
  - calibration improves estimate bias once outcomes exist
"""

import json

import pytest

from app.models.enums import SyncStatus
from app.models.project import Project
from app.models.reference import EstimationOutcome
from app.models.sync import Epic, Task
from app.services import github_pull
from app.services.calibration import accuracy_summary, get_calibration, record_outcomes
from app.services.github_pull import pull_sync_state, resolve_actual_points


# ── actual_points resolution contract ──────────────────────────────────────────

@pytest.mark.parametrize("issue,estimated,expected", [
    ({"state": "closed", "labels": [{"name": "actual-points:8"}]}, 3, 8),   # tier 1
    ({"state": "closed", "labels": [{"name": "points:5"}]}, 3, 5),          # tier 2
    ({"state": "closed", "labels": [{"name": "backend"}]}, 3, 3),           # tier 3 closed -> estimate
    ({"state": "open", "labels": []}, 3, 0),                                # tier 3 open -> 0
    ({"state": "closed", "labels": [{"name": "points:5"}, {"name": "actual-points:2"}]}, 9, 2),  # tier1 wins
])
def test_resolve_actual_points_contract(issue, estimated, expected):
    assert resolve_actual_points(issue, estimated) == expected


# ── pull fixtures ───────────────────────────────────────────────────────────────

def _seed_project_with_epic(db, *, milestone=1, issue=101, estimated=5):
    proj = Project(name="P", sync_config={"github_repo": "demo"})
    db.add(proj)
    db.flush()
    epic = Epic(
        project_id=proj.id, title="Epic A", estimated_points=estimated,
        github_milestone_number=milestone, sync_status=SyncStatus.synced,
    )
    db.add(epic)
    db.flush()
    task = Task(
        epic_id=epic.id, title="Task 1", estimated_points=estimated,
        github_issue_number=issue, sync_status=SyncStatus.synced,
        labels=json.dumps(["backend"]),
    )
    db.add(task)
    db.commit()
    return proj, epic, task


def _patch_github(monkeypatch, *, issue_state="closed", actual_label="actual-points:8",
                  milestone_state="closed"):
    def fake_issues(repo, milestone):
        labels = [{"name": "backend"}]
        if actual_label:
            labels.append({"name": actual_label})
        return [{
            "number": 101,
            "state": issue_state,
            "closed_at": "2026-06-10T12:00:00Z" if issue_state == "closed" else None,
            "labels": labels,
        }]

    def fake_milestone(repo, number):
        return {"number": number, "state": milestone_state,
                "closed_at": "2026-06-10T12:00:00Z" if milestone_state == "closed" else None}

    monkeypatch.setattr(github_pull, "get_github_repo_issues", fake_issues)
    monkeypatch.setattr(github_pull, "get_milestone", fake_milestone)


# ── pull behaviour ──────────────────────────────────────────────────────────────

def test_pull_fills_actuals_and_state(db_session, monkeypatch):
    proj, epic, task = _seed_project_with_epic(db_session)
    _patch_github(monkeypatch)

    counts = pull_sync_state(proj, db_session)

    db_session.refresh(task)
    db_session.refresh(epic)
    assert task.remote_state == "closed"
    assert task.actual_points == 8           # tier-1 label
    assert task.closed_at is not None
    assert epic.actual_points == 8
    assert epic.remote_state == "closed"
    assert counts["updated"] == 1
    assert counts["closed"] == 1


def test_pull_is_idempotent(db_session, monkeypatch):
    proj, epic, task = _seed_project_with_epic(db_session)
    _patch_github(monkeypatch)

    first = pull_sync_state(proj, db_session)
    snap = (task.actual_points, task.remote_state, epic.actual_points, epic.remote_state)
    second = pull_sync_state(proj, db_session)

    assert first == second
    assert (task.actual_points, task.remote_state, epic.actual_points, epic.remote_state) == snap


# ── feedback loop / calibration ─────────────────────────────────────────────────

def test_record_outcomes_then_calibration_factor(db_session, monkeypatch):
    proj, epic, task = _seed_project_with_epic(db_session, estimated=5)
    _patch_github(monkeypatch)  # actual = 8 vs estimated 5 -> ratio 1.6
    pull_sync_state(proj, db_session)

    written = record_outcomes(proj, db_session)
    assert written == 1
    # idempotent: second call writes nothing
    assert record_outcomes(proj, db_session) == 0

    # one sample < MIN_SAMPLES -> still cold start
    assert get_calibration(db_session)["bucket"] == "cold_start"

    # add two more outcomes to cross MIN_SAMPLES
    for _ in range(2):
        db_session.add(EstimationOutcome(
            project_id=proj.id, domain=None, category="backend",
            estimated_points=5, actual_points=8,
        ))
    db_session.commit()

    cal = get_calibration(db_session)
    assert cal["samples"] == 3
    assert cal["factor"] == pytest.approx(1.6, abs=0.01)   # team consistently under-estimates


def test_accuracy_summary_reports_bias(db_session, monkeypatch):
    proj, epic, task = _seed_project_with_epic(db_session, estimated=5)
    _patch_github(monkeypatch)
    pull_sync_state(proj, db_session)

    acc = accuracy_summary(db_session, project_id=proj.id)
    assert acc["estimated_total"] == 5
    assert acc["actual_total"] == 8
    assert acc["bias_pct"] == pytest.approx(60.0, abs=0.1)   # under-estimated by 60%


def test_pull_endpoint_marks_complete(client, db_session, monkeypatch):
    proj, epic, task = _seed_project_with_epic(db_session)
    _patch_github(monkeypatch)

    resp = client.post(f"/api/v1/projects/{proj.id}/sync/pull")
    assert resp.status_code == 200
    body = resp.json()
    assert body["closed"] == 1
    assert body["project_complete"] is True
    assert body["outcomes_recorded"] == 1
