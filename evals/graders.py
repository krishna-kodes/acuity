"""Eval graders for the Acuity AI PM Tool.

Each grader has the signature:
    grade_X(actual: dict, expected: dict, context: dict) -> GradeResult

`actual`  — the response produced by the system under test (runner output)
`expected` — the ground-truth fields from test_cases.json
`context`  — the full test case dict (includes input, max_tool_iterations, etc.)

Skip guard: when a grader's required `expected` key is absent, it returns
GradeResult(passed=True, score=1.0, reasoning="N/A — grader skipped") so
absent graders do not distort pass-rate denominators.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency guards
# ---------------------------------------------------------------------------

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    from ragas.metrics import context_recall as _ragas_context_recall
    _RAGAS_AVAILABLE = True
except Exception:
    _RAGAS_AVAILABLE = False

try:
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase
    _DEEPEVAL_AVAILABLE = True
except Exception:
    _DEEPEVAL_AVAILABLE = False

try:
    from google import genai as _google_genai
    _GENAI_AVAILABLE = True
except Exception:
    _GENAI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Settings (mirrors backend/app/config.py pattern)
# ---------------------------------------------------------------------------

class EvalSettings(BaseSettings):
    google_api_key: str = ""
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    groundedness_threshold: float = 0.7
    fast_llm_model: str = "gpt-5.4-nano"
    main_llm_model: str = "gpt-5.4-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


eval_settings = EvalSettings()


# ---------------------------------------------------------------------------
# GradeResult
# ---------------------------------------------------------------------------

@dataclass
class GradeResult:
    passed: bool
    score: float
    reasoning: str
    metadata: dict = field(default_factory=dict)


def _skip(reason: str = "N/A — grader skipped") -> GradeResult:
    return GradeResult(passed=True, score=1.0, reasoning=reason)


def _unavailable(lib: str) -> GradeResult:
    return GradeResult(
        passed=False, score=0.0,
        reasoning=f"Library not available: {lib}. Install evals/requirements.txt."
    )


# ---------------------------------------------------------------------------
# Canonical groundedness judge prompt (REGRESSION — do not change)
# ---------------------------------------------------------------------------

# REGRESSION: do not change this prompt without re-running evals/regression_suite.py
GROUNDEDNESS_JUDGE_PROMPT = """
System: You are an evaluation judge. Answer only with a JSON object.
User:
  Context: {retrieved_chunks}
  Response: {llm_response}
  Question: Is every factual claim in the Response directly supported by the Context?
  Score 0-1 where 1 = fully grounded, 0 = contains unsupported claims.
  Output: {{"score": float, "reasoning": str, "unsupported_claims": list[str]}}
"""


# ---------------------------------------------------------------------------
# LLM helper (google-genai)
# ---------------------------------------------------------------------------

def _llm_judge(prompt: str) -> dict:
    """Call google-genai fast model and parse JSON response. Returns {} on failure."""
    if not _GENAI_AVAILABLE:
        raise RuntimeError("google-genai not installed")
    if not eval_settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set")
    client = _google_genai.Client(api_key=eval_settings.google_api_key)
    response = client.models.generate_content(
        model=eval_settings.fast_llm_model,
        contents=prompt,
    )
    text = response.text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


# ---------------------------------------------------------------------------
# Cosine similarity helper (numpy)
# ---------------------------------------------------------------------------

def _cosine(a: list[float], b: list[float]) -> float:
    if not _NUMPY_AVAILABLE:
        return 0.5
    va = np.array(a, dtype=float)
    vb = np.array(b, dtype=float)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ---------------------------------------------------------------------------
# Grader 1: retrieval_source_match
# ---------------------------------------------------------------------------

def grade_retrieval_source_match(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("retrieved_chunk_ids"):
        return _skip()
    expected_ids = set(expected["retrieved_chunk_ids"])
    actual_ids = set(actual.get("retrieved_chunk_ids", []))
    if not expected_ids:
        return _skip("No expected chunk IDs — skipped")
    if _RAGAS_AVAILABLE:
        # Use set recall as proxy (RAGAS full pipeline requires dataset setup)
        score = len(actual_ids & expected_ids) / len(expected_ids)
    else:
        score = len(actual_ids & expected_ids) / len(expected_ids)
    passed = score >= 0.80
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"Recall {score:.2f}: found {len(actual_ids & expected_ids)}/{len(expected_ids)} expected chunks",
        metadata={"actual_ids": list(actual_ids), "expected_ids": list(expected_ids)},
    )


# ---------------------------------------------------------------------------
# Grader 2: answer_relevancy
# ---------------------------------------------------------------------------

def grade_answer_relevancy(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("answer_query"):
        return _skip()
    query = context.get("input", {}).get("query", expected["answer_query"])
    answer = actual.get("answer_text", "")
    if not answer:
        return GradeResult(passed=False, score=0.0, reasoning="No answer_text in actual response")
    # Fallback: simple keyword overlap heuristic (RAGAS needs full dataset setup)
    query_tokens = set(query.lower().split())
    answer_tokens = set(answer.lower().split())
    overlap = len(query_tokens & answer_tokens) / max(len(query_tokens), 1)
    # Generous scoring: keyword overlap is a weak proxy
    score = min(1.0, overlap * 3)
    passed = score >= 0.75
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"Keyword overlap heuristic: {overlap:.2f} (×3 = {score:.2f}). RAGAS not used.",
    )


# ---------------------------------------------------------------------------
# Grader 3: reranker_precision_improvement
# ---------------------------------------------------------------------------

def grade_reranker_precision_improvement(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("reranked_chunk_ids"):
        return _skip()
    pre = actual.get("pre_rerank_chunk_ids", [])
    post = actual.get("reranked_chunk_ids", [])
    if not pre or not post:
        return GradeResult(passed=False, score=0.0, reasoning="pre_rerank_chunk_ids or reranked_chunk_ids missing from actual")
    expected_top = expected["reranked_chunk_ids"][0] if expected["reranked_chunk_ids"] else None
    if not expected_top:
        return _skip("No expected top chunk — skipped")
    pre_rank = pre.index(expected_top) if expected_top in pre else len(pre)
    post_rank = post.index(expected_top) if expected_top in post else len(post)
    improved = post_rank < pre_rank
    score = 1.0 if improved else 0.0
    return GradeResult(
        passed=improved, score=score,
        reasoning=f"Top chunk '{expected_top}': pre-rank={pre_rank}, post-rank={post_rank}. {'Improved' if improved else 'No improvement'}.",
    )


# ---------------------------------------------------------------------------
# Grader 4: tbd_explicit_detection
# ---------------------------------------------------------------------------

def grade_tbd_explicit_detection(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    level1_expected = [t for t in expected.get("tbd_items", []) if t.get("level") == 1]
    if not level1_expected:
        return _skip()
    actual_tbds = actual.get("tbd_items", [])
    matched = 0
    missing = []
    for exp_item in level1_expected:
        keyword = exp_item.get("contains", "").lower()
        found = any(
            item.get("level") == 1 and keyword in item.get("text", "").lower()
            for item in actual_tbds
        )
        if found:
            matched += 1
        else:
            missing.append(keyword)
    score = matched / len(level1_expected) if level1_expected else 1.0
    passed = score == 1.0
    reasoning = (
        f"Detected {matched}/{len(level1_expected)} Level-1 TBD items."
        + (f" Missing: {missing}" if missing else "")
    )
    return GradeResult(passed=passed, score=round(score, 4), reasoning=reasoning)


# ---------------------------------------------------------------------------
# Grader 5: tbd_vague_detection
# ---------------------------------------------------------------------------

def grade_tbd_vague_detection(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    level2_expected = [t for t in expected.get("tbd_items", []) if t.get("level") == 2]
    if not level2_expected:
        return _skip()
    if not _GENAI_AVAILABLE or not eval_settings.google_api_key:
        return GradeResult(
            passed=False, score=0.0,
            reasoning="GOOGLE_API_KEY not set — LLM-as-judge unavailable for vague TBD detection",
        )
    actual_tbds = actual.get("tbd_items", [])
    actual_level2_texts = [t.get("text", "") for t in actual_tbds if t.get("level") == 2]
    keywords = [t.get("contains", "") for t in level2_expected]
    prompt = (
        f"You are an evaluation judge. Given these vague requirement keywords: {keywords}\n"
        f"And these detected Level-2 TBD items: {actual_level2_texts}\n"
        f"Score 0-1: how many of the expected vague items were correctly flagged?\n"
        f'Return only JSON: {{"score": float, "reasoning": str}}'
    )
    try:
        result = _llm_judge(prompt)
        score = float(result.get("score", 0.0))
        passed = score >= 0.70
        return GradeResult(passed=passed, score=round(score, 4), reasoning=result.get("reasoning", ""))
    except Exception as exc:
        return GradeResult(passed=False, score=0.0, reasoning=f"LLM judge error: {exc}")


# ---------------------------------------------------------------------------
# Grader 6: tool_selection_accuracy
# ---------------------------------------------------------------------------

def grade_tool_selection_accuracy(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("tool_calls"):
        return _skip()
    expected_tools = set(expected["tool_calls"])
    actual_tools = set(actual.get("tool_calls", []))
    score = len(actual_tools & expected_tools) / max(len(expected_tools), 1)
    # Always passed — this grader is informational only
    return GradeResult(
        passed=True, score=round(score, 4),
        reasoning=f"Tool overlap: {actual_tools & expected_tools} / expected {expected_tools}",
        metadata={"actual_tools": list(actual_tools), "expected_tools": list(expected_tools)},
    )


# ---------------------------------------------------------------------------
# Grader 7: loop_safety
# ---------------------------------------------------------------------------

def grade_loop_safety(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    max_iter = context.get("max_tool_iterations", 10)
    actual_calls = actual.get("tool_calls", [])
    count = len(actual_calls)
    passed = count <= max_iter
    score = 1.0 if passed else 0.0
    return GradeResult(
        passed=passed, score=score,
        reasoning=f"{count} tool calls vs max_tool_iterations={max_iter}. {'OK' if passed else 'EXCEEDED'}",
    )


# ---------------------------------------------------------------------------
# Grader 8: tool_argument_validity
# ---------------------------------------------------------------------------

def grade_tool_argument_validity(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("tool_args_schema"):
        return _skip()
    from evals.tool_schemas import TOOL_ARG_SCHEMAS
    calls_with_args = actual.get("tool_calls_with_args", [])
    if not calls_with_args:
        return _skip("No tool_calls_with_args in actual — skipped")
    total = 0
    valid = 0
    errors = []
    for call in calls_with_args:
        name = call.get("name", "")
        args = call.get("args", {})
        schema = TOOL_ARG_SCHEMAS.get(name)
        if schema is None:
            continue
        total += 1
        try:
            schema(**args)
            valid += 1
        except Exception as exc:
            errors.append(f"{name}: {exc}")
    if total == 0:
        return _skip("No validatable tool calls found")
    score = valid / total
    passed = score == 1.0
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"{valid}/{total} tool calls passed Pydantic validation." + (f" Errors: {errors}" if errors else ""),
    )


# ---------------------------------------------------------------------------
# Grader 9: phase_ordering_compliance
# ---------------------------------------------------------------------------

def grade_phase_ordering_compliance(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("phase_status"):
        return _skip()
    target_phase = context.get("input", {}).get("target_phase")
    exp_http = expected.get("http_status")
    act_http = actual.get("http_status")
    if exp_http == 409:
        passed = act_http == 409
        score = 1.0 if passed else 0.0
        return GradeResult(
            passed=passed, score=score,
            reasoning=f"Expected HTTP 409 (phase gate). Got {act_http}.",
        )
    # Check prior phase complete
    if target_phase:
        prior_key = f"phase_{target_phase - 1}"
        phase_status = actual.get("phase_status", {})
        passed = phase_status.get(prior_key) == "complete"
        score = 1.0 if passed else 0.0
        return GradeResult(
            passed=passed, score=score,
            reasoning=f"Phase {target_phase - 1} status: {phase_status.get(prior_key, 'missing')} (expected 'complete')",
        )
    return _skip("No target_phase in context input — skipped")


# ---------------------------------------------------------------------------
# Grader 10: effort_estimate_plausibility
# ---------------------------------------------------------------------------

def grade_effort_estimate_plausibility(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("effort_range"):
        return _skip()
    er = expected["effort_range"]
    total_weeks = actual.get("total_weeks")
    if total_weeks is None:
        return GradeResult(passed=False, score=0.0, reasoning="total_weeks missing from actual response")
    min_w = er.get("total_weeks_min", 0)
    max_w = er.get("total_weeks_max", float("inf"))
    in_range = min_w <= total_weeks <= max_w
    historical = context.get("input", {}).get("historical_range_weeks")
    ratio_ok = True
    ratio_reasoning = ""
    if historical and in_range:
        max_ratio = er.get("comparable_max_ratio", 3.0)
        max_hist = max(historical)
        ratio_ok = total_weeks <= max_hist * max_ratio
        ratio_reasoning = f" Ratio check: {total_weeks} <= {max_hist} × {max_ratio} = {max_hist * max_ratio}: {'OK' if ratio_ok else 'FAIL'}."
    passed = in_range and ratio_ok
    score = 1.0 if passed else 0.0
    return GradeResult(
        passed=passed, score=score,
        reasoning=f"total_weeks={total_weeks}, range=[{min_w}, {max_w}], in_range={in_range}.{ratio_reasoning}",
    )


# ---------------------------------------------------------------------------
# Grader 11: github_ticket_structure
# ---------------------------------------------------------------------------

def grade_github_ticket_structure(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("github_tickets"):
        return _skip()
    gt = expected["github_tickets"]
    epics = actual.get("epics", [])
    if not epics:
        return GradeResult(passed=False, score=0.0, reasoning="No epics in actual response")
    total = 0
    valid = 0
    errors = []
    for epic in epics:
        total += 1
        if gt.get("epics_as_milestones") and epic.get("github_milestone_number") is None:
            errors.append(f"Epic '{epic.get('title')}' missing github_milestone_number")
        else:
            valid += 1
        for task in epic.get("tasks", []):
            total += 1
            task_ok = True
            if gt.get("tasks_as_issues") and task.get("github_issue_number") is None:
                errors.append(f"Task '{task.get('title')}' missing github_issue_number")
                task_ok = False
            if gt.get("task_label_required"):
                labels = task.get("labels", [])
                if gt["task_label_required"] not in labels:
                    errors.append(f"Task '{task.get('title')}' missing label '{gt['task_label_required']}'")
                    task_ok = False
            if gt.get("milestone_number_required") and task.get("milestone_number") is None:
                errors.append(f"Task '{task.get('title')}' missing milestone_number")
                task_ok = False
            if task_ok:
                valid += 1
    score = valid / total if total else 1.0
    passed = score == 1.0
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"{valid}/{total} items passed structure check." + (f" Errors: {errors[:3]}" if errors else ""),
    )


# ---------------------------------------------------------------------------
# Grader 12: round_trip_sync
# ---------------------------------------------------------------------------

def grade_round_trip_sync(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("round_trip"):
        return _skip()
    rt = expected["round_trip"]
    epics = actual.get("epics", [])
    if not epics:
        return GradeResult(passed=False, score=0.0, reasoning="No epics in round-trip actual")
    checks = []
    if rt.get("epics_have_milestone_number"):
        ok = all(e.get("github_milestone_number") is not None for e in epics)
        checks.append(("epics_have_milestone_number", ok))
    all_tasks = [t for e in epics for t in e.get("tasks", [])]
    if rt.get("tasks_have_issue_number") and all_tasks:
        ok = all(t.get("github_issue_number") is not None for t in all_tasks)
        checks.append(("tasks_have_issue_number", ok))
    if rt.get("sync_status_not_pending"):
        ok = actual.get("sync_status") not in (None, "pending")
        checks.append(("sync_status_not_pending", ok))
    if not checks:
        return _skip("No round-trip checks configured")
    passed_count = sum(1 for _, ok in checks if ok)
    score = passed_count / len(checks)
    passed = score >= 0.90
    failed_checks = [name for name, ok in checks if not ok]
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"{passed_count}/{len(checks)} round-trip checks passed." + (f" Failed: {failed_checks}" if failed_checks else ""),
    )


# ---------------------------------------------------------------------------
# Grader 13: semantic_relevance
# ---------------------------------------------------------------------------

def grade_semantic_relevance(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("retrieved_chunk_ids"):
        return _skip()
    if not _NUMPY_AVAILABLE:
        return _unavailable("numpy")
    query_emb = actual.get("query_embedding")
    chunk_embs = actual.get("chunk_embeddings", [])
    if not query_emb or not chunk_embs:
        return GradeResult(
            passed=False, score=0.0,
            reasoning="query_embedding or chunk_embeddings missing from actual. Real runner required.",
        )
    import numpy as np
    mean_chunk = np.mean(chunk_embs, axis=0).tolist()
    score = _cosine(query_emb, mean_chunk)
    passed = score >= 0.70
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"Cosine similarity (query vs mean chunk embedding): {score:.4f}",
    )


# ---------------------------------------------------------------------------
# Grader 14: groundedness
# ---------------------------------------------------------------------------

def grade_groundedness(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if "groundedness_min" not in expected:
        return _skip()
    if not _GENAI_AVAILABLE or not eval_settings.google_api_key:
        return GradeResult(
            passed=False, score=0.0,
            reasoning="GOOGLE_API_KEY not set — LLM groundedness judge unavailable",
        )
    retrieved = actual.get("retrieved_chunks", actual.get("answer_text", ""))
    response = actual.get("answer_text", "")
    if not response:
        return GradeResult(passed=False, score=0.0, reasoning="No answer_text in actual response")
    prompt = GROUNDEDNESS_JUDGE_PROMPT.format(
        retrieved_chunks=retrieved,
        llm_response=response,
    )
    try:
        result = _llm_judge(prompt)
        score = float(result.get("score", 0.0))
        threshold = float(expected["groundedness_min"])
        passed = score >= threshold
        return GradeResult(
            passed=passed, score=round(score, 4),
            reasoning=result.get("reasoning", ""),
            metadata={"unsupported_claims": result.get("unsupported_claims", [])},
        )
    except Exception as exc:
        return GradeResult(passed=False, score=0.0, reasoning=f"Groundedness judge error: {exc}")


# ---------------------------------------------------------------------------
# Grader 15: proposal_completeness
# ---------------------------------------------------------------------------

_PROPOSAL_SECTIONS = [
    "problem statement",
    "proposed solution",
    "technical architecture",
    "team",
    "timeline",
    "risks",
]


def grade_proposal_completeness(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("proposal_text"):
        return _skip()
    threshold = expected.get("proposal_completeness_min", 0.75)
    proposal_text = actual.get("proposal_text", "")
    if not proposal_text:
        fixture_path = expected.get("proposal_text", "")
        if fixture_path and fixture_path.startswith("fixtures/"):
            try:
                with open(fixture_path) as f:
                    proposal_text = f.read()
            except FileNotFoundError:
                pass
    if not proposal_text:
        return GradeResult(passed=False, score=0.0, reasoning="No proposal_text available")
    if _DEEPEVAL_AVAILABLE and eval_settings.google_api_key:
        try:
            criteria = (
                "Does the proposal contain all of: Problem Statement, Proposed Solution, "
                "Technical Architecture, Team, Timeline, and Risks sections with substantive content?"
            )
            test_case = LLMTestCase(input=criteria, actual_output=proposal_text)
            metric = GEval(name="ProposalCompleteness", criteria=criteria, threshold=threshold)
            metric.measure(test_case)
            score = metric.score
            passed = score >= threshold
            return GradeResult(passed=passed, score=round(score, 4), reasoning=metric.reason or "DeepEval G-Eval")
        except Exception as exc:
            logger.warning("DeepEval G-Eval failed, falling back to section check: %s", exc)
    # Fallback: section presence check
    text_lower = proposal_text.lower()
    found = sum(1 for s in _PROPOSAL_SECTIONS if s in text_lower)
    score = found / len(_PROPOSAL_SECTIONS)
    passed = score >= threshold
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"Section presence: {found}/{len(_PROPOSAL_SECTIONS)} required sections found (fallback check)",
    )


# ---------------------------------------------------------------------------
# Grader 16: tech_stack_rationale_quality
# ---------------------------------------------------------------------------

def grade_tech_stack_rationale_quality(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if not expected.get("tech_stack"):
        return _skip()
    ts_expected = expected["tech_stack"]
    if ts_expected.get("rationale_quality_min") is None and not ts_expected.get("approved_only"):
        return _skip()
    threshold = ts_expected.get("rationale_quality_min", 0.70)
    # Approved-only check (binary gate — overrides G-Eval)
    if ts_expected.get("approved_only"):
        all_approved = actual.get("all_approved", False)
        if not all_approved:
            return GradeResult(
                passed=False, score=0.0,
                reasoning="Tech stack contains unapproved technologies (approved_only check failed)",
            )
    rationale = actual.get("rationale", "")
    if not rationale:
        return GradeResult(passed=False, score=0.0, reasoning="No rationale in actual response")
    if _DEEPEVAL_AVAILABLE and eval_settings.google_api_key:
        try:
            criteria = (
                "Does the rationale reference at least one employee skill, explain why each "
                "technology was chosen, and avoid generic unsupported statements?"
            )
            test_case = LLMTestCase(input=criteria, actual_output=rationale)
            metric = GEval(name="TechStackRationale", criteria=criteria, threshold=threshold)
            metric.measure(test_case)
            score = metric.score
            passed = score >= threshold
            return GradeResult(passed=passed, score=round(score, 4), reasoning=metric.reason or "DeepEval G-Eval")
        except Exception as exc:
            logger.warning("DeepEval G-Eval failed, falling back to keyword check: %s", exc)
    # Fallback: keyword heuristic
    keywords = ["skill", "experience", "team", "because", "chosen", "selected", "recommended"]
    text_lower = rationale.lower()
    found = sum(1 for k in keywords if k in text_lower)
    score = min(1.0, found / 3)
    passed = score >= threshold
    return GradeResult(
        passed=passed, score=round(score, 4),
        reasoning=f"Rationale keyword heuristic: {found}/{len(keywords)} keywords present (fallback)",
    )


# ---------------------------------------------------------------------------
# Grader dispatch
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Grader 17: http_status_check
# ---------------------------------------------------------------------------

def grade_http_status_check(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if "http_status" not in expected:
        return _skip()
    exp_status = expected["http_status"]
    act_status = actual.get("http_status")
    passed = act_status == exp_status
    score = 1.0 if passed else 0.0
    reasoning = f"Expected HTTP {exp_status}, got {act_status}."
    if passed and expected.get("error_contains"):
        needle = expected["error_contains"]
        error_body = str(actual.get("error_contains", actual.get("error_body", "")))
        contains_ok = needle in error_body
        if not contains_ok:
            passed = False
            score = 0.5
            reasoning += f" But error body missing '{needle}'."
    return GradeResult(passed=passed, score=score, reasoning=reasoning)


# ---------------------------------------------------------------------------
# Grader 18: document_ingestion_check
# ---------------------------------------------------------------------------

def grade_document_ingestion_check(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    if "document_status" not in expected and "chroma_chunk_count_min" not in expected:
        return _skip()
    checks = []
    if "document_status" in expected:
        ok = actual.get("document_status") == expected["document_status"]
        checks.append(("document_status", ok,
                        f"document_status={actual.get('document_status')} (expected {expected['document_status']})"))
    if "chroma_chunk_count_min" in expected:
        count = actual.get("chroma_chunk_count", 0)
        ok = count >= expected["chroma_chunk_count_min"]
        checks.append(("chroma_chunk_count_min", ok,
                        f"chroma_chunk_count={count} (min {expected['chroma_chunk_count_min']})"))
    passed = all(ok for _, ok, _ in checks)
    score = 1.0 if passed else 0.0
    reasoning = " | ".join(msg for _, _, msg in checks)
    return GradeResult(passed=passed, score=score, reasoning=reasoning)


# ---------------------------------------------------------------------------
# Grader 19: domain_classifier_accuracy
# ---------------------------------------------------------------------------

def grade_domain_classifier_accuracy(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    """Check domain classifier is_pm_related matches expected value."""
    if "expected_is_pm_related" not in expected:
        return _skip()
    exp = expected["expected_is_pm_related"]
    got = actual.get("is_pm_related")
    passed = got == exp
    return GradeResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reasoning=f"Expected is_pm_related={exp}, got {got!r}",
    )


# ---------------------------------------------------------------------------
# Grader 20: retrieval_gate_precision
# ---------------------------------------------------------------------------

def grade_retrieval_gate_precision(
    actual: dict, expected: dict, context: dict
) -> GradeResult:
    """Check retrieval gate status matches expected outcome."""
    if "expected_gate_status" not in expected:
        return _skip()
    exp = expected["expected_gate_status"]
    got = actual.get("gate_status")
    passed = got == exp
    return GradeResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reasoning=f"Expected gate_status={exp!r}, got {got!r}",
    )


# ---------------------------------------------------------------------------
# Structured proposal graders (template_version=1.0)
# ---------------------------------------------------------------------------

def grade_section_presence(actual: dict, expected: dict, context: dict) -> GradeResult:
    """Check all required section IDs are present in the structured proposal response."""
    required = expected.get("required_section_ids")
    if not required:
        return _skip("required_section_ids not specified")

    sections = actual.get("structured_sections") or actual.get("sections") or []
    present = {s["section_id"] for s in sections if isinstance(s, dict) and "section_id" in s}
    required_set = set(required)
    missing = required_set - present
    score = len(present & required_set) / len(required_set) if required_set else 1.0
    passed = score >= expected.get("section_presence_min", 1.0)
    return GradeResult(
        passed=passed,
        score=score,
        reasoning=f"Present: {sorted(present & required_set)}, Missing: {sorted(missing)}",
        metadata={"missing": sorted(missing)},
    )


def grade_open_questions_determinism(actual: dict, expected: dict, context: dict) -> GradeResult:
    """Assert open_questions section contains exactly N items matching TBD clarifications."""
    exact = expected.get("open_questions_count_exact")
    if exact is None:
        return _skip("open_questions_count_exact not specified")

    sections = actual.get("structured_sections") or []
    oq = next((s for s in sections if isinstance(s, dict) and s.get("section_id") == "open_questions"), None)
    if oq is None:
        return GradeResult(passed=False, score=0.0, reasoning="open_questions section not found in response")

    items = oq.get("items") or []
    count = len(items)
    passed = count == exact
    return GradeResult(
        passed=passed,
        score=1.0 if passed else 0.0,
        reasoning=f"Expected {exact} items, got {count}",
        metadata={"expected": exact, "actual": count},
    )


def grade_risks_grounding(actual: dict, expected: dict, context: dict) -> GradeResult:
    """Verify risks_and_mitigations items are traceable to OOS clarifications or RAG chunks.

    # REGRESSION: do not change this prompt without re-running evals/regression_suite.py
    """
    threshold = expected.get("risks_groundedness_min", 0.70)
    sections = actual.get("structured_sections") or []
    risks_sec = next(
        (s for s in sections if isinstance(s, dict) and s.get("section_id") == "risks_and_mitigations"),
        None,
    )
    if risks_sec is None:
        return GradeResult(passed=False, score=0.0, reasoning="risks_and_mitigations section not found")

    items = risks_sec.get("items") or []
    if not items:
        return GradeResult(passed=True, score=1.0, reasoning="No risk items to ground — vacuously pass")

    oos_items = actual.get("oos_clarifications", [])
    rag_chunks = actual.get("retrieved_chunks", "")
    context_text = "\n".join(str(o) for o in oos_items) + "\n" + str(rag_chunks)
    response_text = "\n".join(
        f"Risk: {item.get('risk','')} | Mitigation: {item.get('mitigation','')}"
        for item in items
        if isinstance(item, dict)
    )

    try:
        prompt = GROUNDEDNESS_JUDGE_PROMPT.format(
            retrieved_chunks=context_text[:3000],
            llm_response=response_text,
        )
        result = _llm_judge(prompt)
        score = float(result.get("score", 0.0))
        passed = score >= threshold
        return GradeResult(
            passed=passed,
            score=score,
            reasoning=result.get("reasoning", ""),
            metadata={"unsupported": result.get("unsupported_claims", [])},
        )
    except Exception as exc:
        return GradeResult(passed=False, score=0.0, reasoning=f"Judge error: {exc}")


def grade_section_completeness(actual: dict, expected: dict, context: dict) -> GradeResult:
    """Run G-Eval style rubric per section; score = mean across sections.

    # REGRESSION: do not change this prompt without re-running evals/regression_suite.py
    """
    threshold = expected.get("section_completeness_min", 0.75)
    sections = actual.get("structured_sections") or []
    if not sections:
        return _skip("structured_sections not present in actual")

    _SECTION_RUBRIC = """You are a proposal quality evaluator.
Section title: {title}
Section content: {content}
Score this section 0.0–1.0 on completeness, specificity, and relevance to a software PRD.
Output only: {{"score": float, "reasoning": str}}"""

    scores: list[float] = []
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        content = sec.get("content", "")
        if not content or sec.get("status") == "failed":
            scores.append(0.0)
            continue
        try:
            prompt = _SECTION_RUBRIC.format(title=sec.get("title", ""), content=content[:1500])
            result = _llm_judge(prompt)
            scores.append(float(result.get("score", 0.0)))
        except Exception:
            scores.append(0.0)

    if not scores:
        return GradeResult(passed=False, score=0.0, reasoning="No sections scored")

    mean_score = sum(scores) / len(scores)
    return GradeResult(
        passed=mean_score >= threshold,
        score=mean_score,
        reasoning=f"Mean completeness score across {len(scores)} sections: {mean_score:.2f}",
        metadata={"per_section_scores": scores},
    )


def grade_regen_idempotency(actual: dict, expected: dict, context: dict) -> GradeResult:
    """Check cosine similarity >= threshold between two regeneration runs of the same section."""
    threshold = expected.get("regen_similarity_min", 0.85)
    content_1 = actual.get("regen_section_content_1")
    content_2 = actual.get("regen_section_content_2")

    if content_1 is None or content_2 is None:
        return _skip("regen_section_content_1 / regen_section_content_2 not in actual")

    if not _NUMPY_AVAILABLE:
        return _unavailable("numpy")

    if not eval_settings.openai_api_key:
        return GradeResult(passed=False, score=0.0, reasoning="OPENAI_API_KEY not set — cannot embed")

    try:
        import openai
        client = openai.OpenAI(api_key=eval_settings.openai_api_key)
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=[str(content_1), str(content_2)],
            dimensions=1536,
        )
        emb1 = resp.data[0].embedding
        emb2 = resp.data[1].embedding
        sim = _cosine(emb1, emb2)
        return GradeResult(
            passed=sim >= threshold,
            score=sim,
            reasoning=f"Cosine similarity between two regen runs: {sim:.3f} (threshold {threshold})",
        )
    except Exception as exc:
        return GradeResult(passed=False, score=0.0, reasoning=f"Embedding error: {exc}")


GRADER_MAP: dict[str, Any] = {
    "retrieval_source_match": grade_retrieval_source_match,
    "answer_relevancy": grade_answer_relevancy,
    "reranker_precision_improvement": grade_reranker_precision_improvement,
    "tbd_explicit_detection": grade_tbd_explicit_detection,
    "tbd_vague_detection": grade_tbd_vague_detection,
    "tool_selection_accuracy": grade_tool_selection_accuracy,
    "loop_safety": grade_loop_safety,
    "tool_argument_validity": grade_tool_argument_validity,
    "phase_ordering_compliance": grade_phase_ordering_compliance,
    "effort_estimate_plausibility": grade_effort_estimate_plausibility,
    "github_ticket_structure": grade_github_ticket_structure,
    "round_trip_sync": grade_round_trip_sync,
    "semantic_relevance": grade_semantic_relevance,
    "groundedness": grade_groundedness,
    "proposal_completeness": grade_proposal_completeness,
    "tech_stack_rationale_quality": grade_tech_stack_rationale_quality,
    "http_status_check": grade_http_status_check,
    "document_ingestion_check": grade_document_ingestion_check,
    "domain_classifier_accuracy": grade_domain_classifier_accuracy,
    "retrieval_gate_precision": grade_retrieval_gate_precision,
    "section_presence": grade_section_presence,
    "open_questions_determinism": grade_open_questions_determinism,
    "risks_grounding": grade_risks_grounding,
    "section_completeness": grade_section_completeness,
    "regen_idempotency": grade_regen_idempotency,
}


# ---------------------------------------------------------------------------
# Grader determinism classification (CI gate vs report-only)
# ---------------------------------------------------------------------------
#
# Report-only graders invoke an LLM judge, a DeepEval G-Eval rubric, RAGAS, or
# embedding-cosine similarity at runtime. They are non-deterministic and
# network-dependent, so gating CI on them (× n_trials, at a 0.90 bar) produces
# flaky red builds. They are still scored and reported every run, but they do
# NOT decide the CI exit code. Deterministic graders (exact match, schema,
# range, count, status checks) form the hard gate.
REPORT_ONLY_GRADERS: frozenset[str] = frozenset({
    "answer_relevancy",              # RAGAS answer_relevancy / soft keyword proxy
    "tbd_vague_detection",           # LLM-as-judge
    "semantic_relevance",            # embedding cosine
    "groundedness",                  # LLM-as-judge
    "proposal_completeness",         # DeepEval G-Eval
    "tech_stack_rationale_quality",  # DeepEval G-Eval
    "risks_grounding",               # LLM-as-judge
    "section_completeness",          # LLM-as-judge (per-section rubric)
    "regen_idempotency",             # embedding cosine
})

# Deterministic graders are everything in GRADER_MAP not flagged report-only.
DETERMINISTIC_GRADERS: frozenset[str] = frozenset(GRADER_MAP) - REPORT_ONLY_GRADERS


def is_report_only(grader_name: str) -> bool:
    return grader_name in REPORT_ONLY_GRADERS


def select_graders(test_case: dict) -> list[str]:
    """Return applicable grader names for a test case (by expected key presence)."""
    expected = test_case.get("expected", {})
    graders: list[str] = []

    if expected.get("retrieved_chunk_ids"):
        graders += ["retrieval_source_match", "semantic_relevance"]
    if expected.get("answer_query"):
        graders += ["answer_relevancy"]
    if expected.get("reranked_chunk_ids"):
        graders += ["reranker_precision_improvement"]
    level1 = [t for t in expected.get("tbd_items", []) if t.get("level") == 1]
    if level1:
        graders += ["tbd_explicit_detection"]
    level2 = [t for t in expected.get("tbd_items", []) if t.get("level") == 2]
    if level2:
        graders += ["tbd_vague_detection"]
    if expected.get("tool_calls"):
        graders += ["tool_selection_accuracy", "loop_safety"]
    if expected.get("loop_safety") and "loop_safety" not in graders:
        graders += ["loop_safety"]
    if expected.get("tool_args_schema"):
        graders += ["tool_argument_validity"]
    if expected.get("phase_status"):
        graders += ["phase_ordering_compliance"]
    if expected.get("effort_range"):
        graders += ["effort_estimate_plausibility"]
    if expected.get("github_tickets"):
        graders += ["github_ticket_structure"]
    if expected.get("round_trip"):
        graders += ["round_trip_sync"]
    if "groundedness_min" in expected:
        graders += ["groundedness"]
    if expected.get("proposal_text"):
        graders += ["proposal_completeness"]
    if expected.get("tech_stack"):
        ts = expected["tech_stack"]
        if ts.get("rationale_quality_min") is not None or ts.get("approved_only"):
            graders += ["tech_stack_rationale_quality"]

    if "http_status" in expected:
        graders += ["http_status_check"]
    if "document_status" in expected or "chroma_chunk_count_min" in expected:
        graders += ["document_ingestion_check"]
    if "expected_is_pm_related" in expected:
        graders += ["domain_classifier_accuracy"]
    if "expected_gate_status" in expected:
        graders += ["retrieval_gate_precision"]
    if "required_section_ids" in expected:
        graders += ["section_presence"]
    if "open_questions_count_exact" in expected:
        graders += ["open_questions_determinism"]
    if "risks_groundedness_min" in expected:
        graders += ["risks_grounding"]
    if "section_completeness_min" in expected:
        graders += ["section_completeness"]
    if "regen_similarity_min" in expected:
        graders += ["regen_idempotency"]

    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for g in graders:
        if g not in seen:
            seen.add(g)
            result.append(g)
    return result
