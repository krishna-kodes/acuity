"""Layer 4 — Output monitor.

Post-response checks run after LLM generation:
  1. Canary token leak: detects system-prompt exfiltration attempts.
     A secret token is embedded in the system message with instructions
     never to repeat it. If it appears in the LLM response, the model
     was manipulated into leaking its own instructions.

Feature flag: OUTPUT_MONITOR_ENABLED (default true).
"""
from dataclasses import dataclass

from app.config import settings
from app.guardrails import log_guardrail


@dataclass
class OutputMonitorResult:
    canary_leaked: bool
    detail: str | None = None


def evaluate(response: str, project_id: str) -> OutputMonitorResult:
    """Check LLM response for canary token. Never raises."""
    if not settings.output_monitor_enabled:
        return OutputMonitorResult(canary_leaked=False)

    canary = settings.prompt_canary_token
    if canary and canary in response:
        log_guardrail(
            project_id, 4, "canary_leaked", 1.0,
            {"canary_present": True, "response_length": len(response)},
        )
        return OutputMonitorResult(
            canary_leaked=True,
            detail="Response contained session integrity token — possible system prompt exfiltration.",
        )

    return OutputMonitorResult(canary_leaked=False)
