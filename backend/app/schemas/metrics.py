from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_tokens: int
    total_cost_usd: float
    phase_latencies: dict[str, float]
    eval_pass_rate: float
    github_sync_success_rate: float
