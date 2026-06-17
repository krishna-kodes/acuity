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


class DailyTokenItem(BaseModel):
    day: str           # ISO date string e.g. "2026-06-08"
    input_tokens: int
    output_tokens: int
    cost: float


class RetrievalQueryItem(BaseModel):
    query_index: int   # 1-based
    n_retrieved: int
    top_score: float   # highest reranker score — relevancy proxy
    avg_score: float   # mean of all candidate scores — recall proxy


class QualityScoreItem(BaseModel):
    grader: str
    score: float
    source: str        # "live" | "eval_run"


class EstimationEpicItem(BaseModel):
    epic: str
    estimated: int
    actual: int


class EstimationAccuracy(BaseModel):
    per_epic: list[EstimationEpicItem]
    estimated_total: int
    actual_total: int
    bias_pct: float | None         # +ve = under-estimated (actual > estimate)
    mae_pct: float | None          # mean absolute % error across epics
    calibration_factor: float      # multiplier applied to future estimates
    calibration_samples: int       # outcomes backing the factor
    calibration_bucket: str        # which bucket the factor came from


class MetricsResponse(BaseModel):
    # Summary
    total_tokens: int
    total_cost_usd: float
    input_tokens: int
    output_tokens: int
    phase_latencies: dict[str, float]
    eval_pass_rate: float
    github_sync_success_rate: float
    github_sync_fails: int
    # Detailed breakdowns
    tokens_by_phase: list[TokenPhaseItem]
    latency_by_node: list[LatencyNodeItem]
    errors_by_phase: list[ErrorPhaseItem]
    error_count: int
    # New: live data
    daily_token_trend: list[DailyTokenItem]
    retrieval_by_query: list[RetrievalQueryItem]
    quality_scores: list[QualityScoreItem]
    avg_groundedness: float | None
    # Estimation feedback loop (bidirectional sync + calibration)
    estimation_accuracy: EstimationAccuracy
