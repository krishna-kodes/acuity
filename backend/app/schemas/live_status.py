from pydantic import BaseModel

PHASE_AGENT_NAMES = {
    "phase_1": "pii_filter",
    "phase_2": "chat_agent",
    "modules": "module_extractor",
    "phase_3": "stack_advisor",
    "phase_4": "team_planner",
    "phase_5": "effort_estimator",
    "phase_6": "epic_builder",
}


class LiveStatusResponse(BaseModel):
    agent: str | None = None
    model: str | None = None
    total_tokens: int = 0
    session_cost_usd: float = 0.0
    last_node: str | None = None
    last_latency_ms: float | None = None
    llm_call_count: int = 0
    active_phase: str | None = None
    token_budget: int = 100_000
    is_recent: bool = False
