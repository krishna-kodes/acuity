"""Cost guardrail enforcement (MAX_COST_PER_WORKFLOW_USD, ADR-005)."""

from unittest.mock import patch

import pytest

from app.services.metrics_tracker import (
    CostBudgetExceededError,
    enforce_cost_budget,
)


def test_enforce_raises_when_over_budget():
    with patch("app.services.metrics_tracker.project_cost_usd", return_value=0.60), \
         patch("app.services.metrics_tracker.settings") as s:
        s.metrics_enabled = True
        s.max_cost_per_workflow_usd = 0.50
        with pytest.raises(CostBudgetExceededError):
            enforce_cost_budget(1)


def test_enforce_passes_when_under_budget():
    with patch("app.services.metrics_tracker.project_cost_usd", return_value=0.10), \
         patch("app.services.metrics_tracker.settings") as s:
        s.metrics_enabled = True
        s.max_cost_per_workflow_usd = 0.50
        enforce_cost_budget(1)  # no raise


def test_enforce_disabled_when_budget_zero():
    with patch("app.services.metrics_tracker.project_cost_usd", return_value=99.0) as cost, \
         patch("app.services.metrics_tracker.settings") as s:
        s.metrics_enabled = True
        s.max_cost_per_workflow_usd = 0.0
        enforce_cost_budget(1)  # no raise, budget guard disabled
        cost.assert_not_called()


@pytest.mark.asyncio
async def test_with_retry_does_not_retry_budget_error():
    from app.services.workflow import with_retry

    calls = {"n": 0}

    @with_retry(max_retries=3, base_delay=0)
    async def node():
        calls["n"] += 1
        raise CostBudgetExceededError(1, 0.6, 0.5)

    with pytest.raises(CostBudgetExceededError):
        await node()
    assert calls["n"] == 1  # terminal — not retried
