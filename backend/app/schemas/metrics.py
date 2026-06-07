from pydantic import BaseModel


class TokenPhaseItem(BaseModel):
    phase: str
    tokens: int
    cost: float


class LatencyNodeItem(BaseModel):
    node: str
    p50: float
    p95: float


class ErrorPhaseItem(BaseModel):
    phase: str
    errors: int


class MetricsResponse(BaseModel):
    # Summary (existing fields — preserved for API compat)
    total_tokens: int
    total_cost_usd: float
    phase_latencies: dict[str, float]
    eval_pass_rate: float
    github_sync_success_rate: float
    # Detailed breakdowns
    tokens_by_phase: list[TokenPhaseItem]
    latency_by_node: list[LatencyNodeItem]
    errors_by_phase: list[ErrorPhaseItem]
    error_count: int
