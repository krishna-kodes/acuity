from enum import Enum

from pydantic import BaseModel


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"
    skipped = "skipped"
    failed = "failed"


class SyncProvider(str, Enum):
    github = "github"
    jira = "jira"


class SyncConfigRequest(BaseModel):
    provider: SyncProvider | None = None
    github_repo: str | None = None
    jira_project_key: str | None = None


class SyncConfigResponse(BaseModel):
    provider: SyncProvider
    config: SyncConfigRequest


class SyncResponse(BaseModel):
    synced: int
    skipped: int
    failed: int
    status: SyncStatus
    milestones_url: str | None = None


class SeedResult(BaseModel):
    seeded: int
    status: str
