#!/usr/bin/env python3
"""Acuity eval suite CI gate.

Usage:
    python eval_suite.py --threshold 0.90
    python eval_suite.py --threshold 0.0 --output results/baseline_eval_run_001.json
    python eval_suite.py --no-sync
    python eval_suite.py --threshold 0.90 --n-trials 3
    python eval_suite.py --threshold 0.90 --persist-db

Exit codes:
    0 — pass@1 >= threshold
    1 — pass@1 < threshold
"""

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Acuity eval suite CI gate")
    parser.add_argument(
        "--threshold", type=float, default=0.90,
        help="Minimum pass@1 rate to exit 0 (default: 0.90)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Override output filename (default: results/eval_results_{timestamp}.json)",
    )
    parser.add_argument(
        "--no-sync", action="store_true",
        help="Skip rclone sync to Google Drive",
    )
    parser.add_argument(
        "--n-trials", type=int, default=3,
        help="Trials per test case (default: 3)",
    )
    parser.add_argument(
        "--persist-db", action="store_true",
        help="Write eval results to app.db eval_results table (surfaces in /metrics AI Quality tab)",
    )
    args = parser.parse_args()

    # Import here so eval deps missing = clear error message
    try:
        from evals.harness import HybridRAGAgentEval
    except ImportError as exc:
        logger.error("Cannot import eval harness: %s", exc)
        logger.error("Run: pip install -r evals/requirements.txt")
        return 1

    # 1. Run evals
    ev = HybridRAGAgentEval()
    logger.info("Running %d test cases × %d trials ...", len(ev.test_cases), args.n_trials)
    output = ev.run_all(n_trials=args.n_trials)
    pass_rate = output["pass_rate"]
    logger.info("pass@1: %.3f  |  pass@k: %.3f  |  pass^k: %.3f",
                pass_rate, output["pass_at_k"], output["pass_hat_k"])

    # 2. Write results file
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    filename = args.output or f"results/eval_results_{ts}.json"
    Path(filename).parent.mkdir(parents=True, exist_ok=True)

    baseline_path = Path("results/baseline_eval_run_001.json")
    if baseline_path.exists():
        try:
            baseline = json.loads(baseline_path.read_text())
            output["delta_vs_baseline"] = round(pass_rate - baseline.get("pass_rate", 0.0), 4)
            logger.info("delta_vs_baseline: %+.3f", output["delta_vs_baseline"])
        except Exception as exc:
            logger.warning("Could not read baseline: %s", exc)

    Path(filename).write_text(json.dumps(output, indent=2, default=str))
    logger.info("Results written to: %s", filename)

    # 3. Persist to app.db (optional)
    if args.persist_db:
        _persist_to_db(output, ts)

    # 4. rclone sync (warning-only on failure)
    if not args.no_sync:
        _rclone_sync()

    # 5. Per-grader summary
    summary = output.get("summary", {})
    by_grader = summary.get("by_grader", {})
    if by_grader:
        logger.info("--- Grader breakdown ---")
        for grader, stats in sorted(by_grader.items()):
            status = "PASS" if stats["pass_rate"] >= 0.70 else "fail"
            logger.info("  [%s] %-40s pass=%.2f avg_score=%.2f",
                        status, grader, stats["pass_rate"], stats["avg_score"])

    # 6. Exit code
    if pass_rate < args.threshold:
        logger.error("FAIL: pass@1 %.3f < threshold %.3f", pass_rate, args.threshold)
        return 1
    logger.info("PASS: pass@1 %.3f >= threshold %.3f", pass_rate, args.threshold)
    return 0


def _persist_to_db(output: dict, run_id: str) -> None:
    """Write per-grader eval results to app.db so the metrics API can surface them."""
    import sys
    import os
    # Ensure backend is importable when run from repo root
    backend_path = os.path.join(os.path.dirname(__file__), "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    try:
        from app.database import SessionLocal
        from app.models.observability import EvalResult
    except ImportError as exc:
        logger.warning("Cannot import backend models for --persist-db: %s", exc)
        return

    summary = output.get("summary", {})
    by_grader = summary.get("by_grader", {})
    if not by_grader:
        logger.warning("--persist-db: no by_grader data found in output; skipping DB write")
        return

    db = SessionLocal()
    written = 0
    try:
        for grader, stats in by_grader.items():
            db.add(EvalResult(
                run_id=run_id,
                grader=grader,
                passed=stats.get("pass_rate", 0.0) >= 0.70,
                score=round(float(stats.get("avg_score", 0.0)), 4),
                reasoning=None,
            ))
            written += 1
        db.commit()
        logger.info("--persist-db: wrote %d grader results to app.db (run_id=%s)", written, run_id)
    except Exception as exc:
        db.rollback()
        logger.warning("--persist-db: DB write failed: %s", exc)
    finally:
        db.close()


def _rclone_sync() -> None:
    try:
        result = subprocess.run(
            ["rclone", "copy", "results/", "gdrive:acuity/eval-results/"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            logger.warning("rclone warning: %s", result.stderr.strip())
        else:
            logger.info("rclone sync complete.")
    except FileNotFoundError:
        logger.info("rclone not found — skipping Google Drive sync.")
    except subprocess.TimeoutExpired:
        logger.warning("rclone timed out — sync incomplete.")


if __name__ == "__main__":
    sys.exit(main())
