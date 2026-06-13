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


class SyncRequest(BaseModel):
    epic_ids: list[int] | None = None  # None = sync all; list = sync only these IDs


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


class PullSyncResponse(BaseModel):
    updated: int           # tasks refreshed from their remote issue
    closed: int            # tasks now closed on the tracker
    still_open: int        # tasks still open
    skipped_unsynced: int  # epics with no remote milestone yet
    outcomes_recorded: int = 0   # estimation_outcomes rows written this pull
    project_complete: bool = False


class SeedResult(BaseModel):
    seeded: int
    status: str
