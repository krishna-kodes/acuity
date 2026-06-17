"""Eval harness for the Acuity AI PM Tool.

Usage:
    # Run all test cases (mock mode, offline)
    from evals.harness import HybridRAGAgentEval
    ev = HybridRAGAgentEval()
    output = ev.run_all()

    # Single test case
    results = ev.run_eval(ev.test_cases[0])

    # CLI (single test case)
    python -m evals.harness --test-case tc-001

Runner selection:
    EVAL_MODE=mock (default)  — canned responses, no network
    EVAL_MODE=real            — HTTP calls to localhost:8000 (requires API keys)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from evals.graders import (
    GRADER_MAP,
    GradeResult,
    eval_settings,
    is_report_only,
    select_graders,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# EvalResult
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    test_case_id: str
    grader_name: str
    passed: bool
    score: float
    reasoning: str
    trial: int


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

class BaseRunner:
    def run(self, test_case: dict) -> dict:
        raise NotImplementedError


class MockRunner(BaseRunner):
    """Canned responses designed to produce ~40% pass@1 (baseline target).

    Responses are per-test-case. Graders that require embeddings or LLM judge
    calls will fail gracefully (no API keys in mock mode), which intentionally
    contributes to the ~40% baseline pass rate.
    """

    _RESPONSES: dict[str, dict] = {
        # tc-001: explicit TBD — partial: finds SLA but misses "response time"
        "tc-001": {
            "tbd_items": [
                {"level": 1, "text": "SLA: TBD pending stakeholder agreement"},
            ],
            "tool_calls": ["detect_tbds"],
            "answer_text": "The SLA is currently TBD pending stakeholder review.",
            "retrieved_chunk_ids": ["chunk_7"],
        },
        # tc-002: vague TBD — LLM judge unavailable in mock → fails
        "tc-002": {
            "tbd_items": [],
            "answer_text": "Performance and security requirements are vague and need clarification.",
        },
        # tc-003: oversized file → 422
        "tc-003": {
            "http_status": 422,
            "error_contains": "MAX_FILE_SIZE_MB",
        },
        # tc-004: unsupported extension → 422
        "tc-004": {
            "http_status": 422,
        },
        # tc-005: valid ingestion → passes
        "tc-005": {
            "document_status": "ingested",
            "chroma_chunk_count": 5,
        },
        # tc-006: groundedness — LLM judge unavailable in mock → groundedness fails; retrieval partial
        "tc-006": {
            "retrieved_chunk_ids": ["chunk_1"],
            "answer_text": "The system uptime requirement is 99.9% measured monthly.",
            "query_embedding": None,
            "chunk_embeddings": [],
        },
        # tc-007: query rewriting — tool_calls partial
        "tc-007": {
            "tool_calls": ["rewrite_query"],
            "sub_query_count": 2,
        },
        # tc-008: proposal completeness — fixture file read by grader fallback; passes via section check
        "tc-008": {
            "proposal_text": "",
        },
        # tc-009: approved tech only — mock returns approved=True
        "tc-009": {
            "all_approved": True,
            "rationale": "Next.js chosen because frontend team has React experience. FastAPI selected for Python expertise and performance.",
            "tech_stack": {
                "frontend": ["Next.js"],
                "backend": ["FastAPI"],
                "database": ["SQLite"],
                "infra": ["Railway"],
            },
        },
        # tc-010: rationale quality — keyword heuristic fallback, passes
        "tc-010": {
            "all_approved": True,
            "rationale": "Next.js was recommended because the team has React skill and experience. FastAPI was selected because the backend team chose it for performance and Python expertise.",
        },
        # tc-011: phase ordering — returns 409 correctly
        "tc-011": {
            "http_status": 409,
            "phase_status": {"phase_1": "complete", "phase_2": "in_progress"},
        },
        # tc-012: effort plausibility — within range
        "tc-012": {
            "total_weeks": 8.0,
            "total_points": 40,
            "tool_calls": ["get_historical_projects", "estimate_effort"],
        },
        # tc-013: loop safety — within iterations
        "tc-013": {
            "tool_calls": ["get_historical_projects", "estimate_effort"],
        },
        # tc-014: GitHub structure — valid structure
        "tc-014": {
            "epics": [
                {
                    "title": "Epic 1: Backend",
                    "github_milestone_number": 1,
                    "tasks": [
                        {
                            "title": "Task 1.1",
                            "github_issue_number": 10,
                            "labels": ["task"],
                            "milestone_number": 1,
                        }
                    ],
                }
            ]
        },
        # tc-015: round-trip — passes
        "tc-015": {
            "epics": [
                {
                    "title": "Epic 1",
                    "github_milestone_number": 1,
                    "tasks": [
                        {"title": "Task 1", "github_issue_number": 10}
                    ],
                }
            ],
            "sync_status": "synced",
        },
    }

    def run(self, test_case: dict) -> dict:
        return dict(self._RESPONSES.get(test_case["id"], {}))


class RealRunner(BaseRunner):
    """HTTP calls to the running FastAPI server at localhost:8000.

    Phase dispatch:
      Phase 1 → POST /projects/eval-{id}/documents (multipart)
      Phase 2 → POST /projects/eval-{id}/chat {"message": query}
      Phase 3 → POST /projects/eval-{id}/stack
      Phase 5 → POST /projects/eval-{id}/estimate
      Phase 6 → POST /projects/eval-{id}/sync
    """

    BASE_URL = "http://localhost:8000/api/v1"

    def run(self, test_case: dict) -> dict:
        phase = test_case.get("phase", 0)
        inp = test_case.get("input", {})
        project_id = f"eval-{test_case['id']}"

        try:
            if phase == 1:
                return self._run_phase1(project_id, inp)
            elif phase == 2:
                return self._run_phase2(project_id, inp)
            elif phase == 3:
                return self._run_phase3(project_id, inp)
            elif phase == 5:
                return self._run_phase5(project_id, inp)
            elif phase == 6:
                return self._run_phase6(project_id, inp)
            else:
                return {"error": f"No RealRunner handler for phase {phase}"}
        except requests.RequestException as exc:
            logger.error("RealRunner HTTP error for %s: %s", test_case["id"], exc)
            return {"error": str(exc)}

    def _run_phase1(self, project_id: str, inp: dict) -> dict:
        fixture = inp.get("document_fixture", "")
        ext = inp.get("simulate_extension", ".pdf")
        size_mb = inp.get("simulate_size_mb")
        if size_mb:
            content = b"x" * int(size_mb * 1024 * 1024)
        elif fixture and Path(fixture).exists():
            content = Path(fixture).read_bytes()
        else:
            content = b"stub content"
        filename = f"test{ext}"
        resp = requests.post(
            f"{self.BASE_URL}/projects/{project_id}/documents",
            files={"file": (filename, content, "application/pdf")},
            timeout=30,
        )
        return {"http_status": resp.status_code, "document_status": resp.json().get("status")}

    def _run_phase2(self, project_id: str, inp: dict) -> dict:
        query = inp.get("query", "")
        resp = requests.post(
            f"{self.BASE_URL}/projects/{project_id}/chat",
            json={"message": query},
            timeout=60,
        )
        data = resp.json() if resp.ok else {}
        return {
            "answer_text": data.get("text", ""),
            "retrieved_chunk_ids": data.get("retrieved_chunk_ids", []),
            "tbd_items": data.get("tbd_items", []),
            "tool_calls": data.get("tool_calls", []),
            "http_status": resp.status_code,
        }

    def _run_phase3(self, project_id: str, inp: dict) -> dict:
        resp = requests.post(
            f"{self.BASE_URL}/projects/{project_id}/stack",
            timeout=60,
        )
        data = resp.json() if resp.ok else {}
        return {
            "tech_stack": data,
            "rationale": data.get("rationale", ""),
            "all_approved": data.get("all_approved", False),
            "http_status": resp.status_code,
        }

    def _run_phase5(self, project_id: str, inp: dict) -> dict:
        resp = requests.post(
            f"{self.BASE_URL}/projects/{project_id}/estimate",
            timeout=60,
        )
        data = resp.json() if resp.ok else {}
        return {
            "total_weeks": data.get("total_weeks"),
            "total_points": data.get("total_points"),
            "tool_calls": data.get("tool_calls", []),
            "http_status": resp.status_code,
        }

    def _run_phase6(self, project_id: str, inp: dict) -> dict:
        resp = requests.post(
            f"{self.BASE_URL}/projects/{project_id}/sync",
            timeout=60,
        )
        data = resp.json() if resp.ok else {}
        return {
            "epics": data.get("epics", []),
            "sync_status": data.get("status"),
            "http_status": resp.status_code,
        }


# ---------------------------------------------------------------------------
# HybridRAGAgentEval
# ---------------------------------------------------------------------------

class HybridRAGAgentEval:
    def __init__(
        self,
        test_cases_path: str = "test_cases.json",
        runner: BaseRunner | None = None,
    ) -> None:
        self.test_cases = self._load_test_cases(test_cases_path)
        self.runner = runner or self._select_runner()
        self._validate_test_cases()

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------

    def _load_test_cases(self, path: str) -> list[dict]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"test_cases.json not found at {path}")
        return json.loads(p.read_text())

    def _select_runner(self) -> BaseRunner:
        has_keys = bool(eval_settings.google_api_key or eval_settings.anthropic_api_key)
        if os.getenv("EVAL_MODE", "mock") == "real" and has_keys:
            logger.info("Using RealRunner (EVAL_MODE=real)")
            return RealRunner()
        logger.info("Using MockRunner (EVAL_MODE=mock or no API keys)")
        return MockRunner()

    def _validate_test_cases(self) -> None:
        for tc in self.test_cases:
            graders = select_graders(tc)
            if not graders:
                logger.warning(
                    "Test case %s has no applicable graders — check expected fields",
                    tc["id"],
                )

    # ------------------------------------------------------------------
    # Core eval
    # ------------------------------------------------------------------

    def run_eval(self, test_case: dict, n_trials: int = 3) -> list[EvalResult]:
        grader_names = select_graders(test_case)
        if not grader_names:
            logger.warning("No graders for %s — skipping", test_case["id"])
            return []

        results: list[EvalResult] = []
        for trial in range(1, n_trials + 1):
            actual = self.runner.run(test_case)
            for grader_name in grader_names:
                grader_fn = GRADER_MAP[grader_name]
                try:
                    grade: GradeResult = grader_fn(actual, test_case["expected"], test_case)
                except Exception as exc:
                    logger.error("Grader %s crashed on %s: %s", grader_name, test_case["id"], exc)
                    grade = GradeResult(passed=False, score=0.0, reasoning=f"Grader crashed: {exc}")
                results.append(EvalResult(
                    test_case_id=test_case["id"],
                    grader_name=grader_name,
                    passed=grade.passed,
                    score=grade.score,
                    reasoning=grade.reasoning,
                    trial=trial,
                ))
        return results

    def run_all(self, n_trials: int = 3) -> dict:
        all_results: list[EvalResult] = []
        for tc in self.test_cases:
            all_results.extend(self.run_eval(tc, n_trials=n_trials))

        pass_at_1 = self._compute_pass_at_1(all_results)
        pass_at_k = self._compute_pass_at_k(all_results, k=n_trials)
        pass_hat_k = self._compute_pass_hat_k(all_results, k=n_trials)

        # CI gate uses deterministic graders only; LLM-judge/semantic graders
        # are reported but never decide the exit code (they're flaky).
        deterministic = [r for r in all_results if not is_report_only(r.grader_name)]
        report_only = [r for r in all_results if is_report_only(r.grader_name)]
        deterministic_pass_at_1 = self._compute_pass_at_1(deterministic)
        report_only_pass_at_1 = self._compute_pass_at_1(report_only)

        return {
            "pass_rate": pass_at_1,
            "deterministic_pass_rate": deterministic_pass_at_1,
            "report_only_pass_rate": report_only_pass_at_1,
            "pass_at_k": pass_at_k,
            "pass_hat_k": pass_hat_k,
            "results": [asdict(r) for r in all_results],
            "summary": self._build_summary(all_results, n_trials),
        }

    # ------------------------------------------------------------------
    # Metric computations
    # ------------------------------------------------------------------

    def _compute_pass_at_1(self, results: list[EvalResult]) -> float:
        trial1 = [r for r in results if r.trial == 1]
        if not trial1:
            return 0.0
        return round(sum(1 for r in trial1 if r.passed) / len(trial1), 4)

    def _compute_pass_at_k(self, results: list[EvalResult], k: int) -> float:
        """pass@k: fraction of (tc, grader) pairs where at least 1 trial passes."""
        pairs: dict[tuple[str, str], bool] = {}
        for r in results:
            key = (r.test_case_id, r.grader_name)
            pairs[key] = pairs.get(key, False) or r.passed
        if not pairs:
            return 0.0
        return round(sum(pairs.values()) / len(pairs), 4)

    def _compute_pass_hat_k(self, results: list[EvalResult], k: int) -> float:
        """pass^k: fraction of (tc, grader) pairs where ALL trials pass."""
        pair_trials: dict[tuple[str, str], list[bool]] = {}
        for r in results:
            key = (r.test_case_id, r.grader_name)
            pair_trials.setdefault(key, []).append(r.passed)
        if not pair_trials:
            return 0.0
        all_pass = sum(1 for v in pair_trials.values() if all(v))
        return round(all_pass / len(pair_trials), 4)

    def _build_summary(self, results: list[EvalResult], n_trials: int) -> dict:
        trial1 = [r for r in results if r.trial == 1]
        by_phase: dict[str, dict] = {}
        for tc in self.test_cases:
            phase_key = f"phase_{tc['phase']}"
            tc_results = [r for r in trial1 if r.test_case_id == tc["id"]]
            if not tc_results:
                continue
            if phase_key not in by_phase:
                by_phase[phase_key] = {"passed": 0, "total": 0}
            by_phase[phase_key]["total"] += len(tc_results)
            by_phase[phase_key]["passed"] += sum(1 for r in tc_results if r.passed)
        by_phase_rates = {
            k: {"pass_rate": round(v["passed"] / v["total"], 4), "count": v["total"]}
            for k, v in by_phase.items()
            if v["total"] > 0
        }
        by_grader: dict[str, dict] = {}
        for r in trial1:
            if r.grader_name not in by_grader:
                by_grader[r.grader_name] = {"passed": 0, "total": 0, "scores": []}
            by_grader[r.grader_name]["total"] += 1
            if r.passed:
                by_grader[r.grader_name]["passed"] += 1
            by_grader[r.grader_name]["scores"].append(r.score)
        by_grader_summary = {
            k: {
                "pass_rate": round(v["passed"] / v["total"], 4),
                "avg_score": round(sum(v["scores"]) / len(v["scores"]), 4),
                "report_only": is_report_only(k),
            }
            for k, v in by_grader.items()
        }
        return {
            "total_test_cases": len(self.test_cases),
            "total_grader_evaluations": len(trial1),
            "by_phase": by_phase_rates,
            "by_grader": by_grader_summary,
            "runner_mode": "real" if isinstance(self.runner, RealRunner) else "mock",
            "n_trials": n_trials,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Run Acuity eval harness")
    parser.add_argument("--test-case", type=str, help="Run a single test case by ID")
    parser.add_argument("--n-trials", type=int, default=3)
    args = parser.parse_args()

    ev = HybridRAGAgentEval()
    if args.test_case:
        matches = [t for t in ev.test_cases if t["id"] == args.test_case]
        if not matches:
            print(f"Test case '{args.test_case}' not found")
            raise SystemExit(1)
        tc = matches[0]
        results = ev.run_eval(tc, n_trials=args.n_trials)
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"[{status}] trial={r.trial} grader={r.grader_name} score={r.score:.3f} | {r.reasoning[:120]}")
    else:
        output = ev.run_all(n_trials=args.n_trials)
        print(json.dumps(output["summary"], indent=2))
