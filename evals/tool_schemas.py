"""Pydantic arg schemas for LangGraph agent tool calls.

Mirrors the tool signatures in backend/app/mcp/github_server.py and the
agent tool names used in test_cases.json expected.tool_calls.
Used by grade_tool_argument_validity to validate actual tool call args.
"""

from pydantic import BaseModel


class CreateMilestoneArgs(BaseModel):
    repo: str
    title: str
    description: str
    due_date: str


class CreateIssueArgs(BaseModel):
    repo: str
    title: str
    body: str
    milestone_number: int
    labels: list[str]
    assignees: list[str]


class GetRepoIssuesArgs(BaseModel):
    repo: str
    milestone: int


class RewriteQueryArgs(BaseModel):
    query: str
    n: int = 3


class RetrieveChunksArgs(BaseModel):
    queries: list[str]
    top_k: int = 20


class DetectTBDsArgs(BaseModel):
    text: str


class GetHistoricalProjectsArgs(BaseModel):
    domain: str = ""
    limit: int = 10


class EstimateEffortArgs(BaseModel):
    epics: list[dict]
    historical_projects: list[dict]


# Maps tool_name → Pydantic model (None = no schema validation for this tool)
TOOL_ARG_SCHEMAS: dict[str, type[BaseModel] | None] = {
    "create_github_milestone": CreateMilestoneArgs,
    "create_github_issue": CreateIssueArgs,
    "get_github_repo_issues": GetRepoIssuesArgs,
    "rewrite_query": RewriteQueryArgs,
    "retrieve_chunks": RetrieveChunksArgs,
    "detect_tbds": DetectTBDsArgs,
    "get_historical_projects": GetHistoricalProjectsArgs,
    "estimate_effort": EstimateEffortArgs,
}
