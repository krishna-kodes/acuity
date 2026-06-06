from enum import Enum

from pydantic import BaseModel


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"
    skipped = "skipped"
    failed = "failed"


class SyncResponse(BaseModel):
    synced: int
    skipped: int
    failed: int
    status: SyncStatus


class SeedResult(BaseModel):
    seeded: int
    status: str
