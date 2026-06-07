from typing import Literal

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    status: str
    upload_ts: str


class RedactionDecisionItem(BaseModel):
    detection_id: int
    confirmed: bool   # True = apply redaction; False = override (keep original)


class RedactionDecisionsUpdate(BaseModel):
    decisions: list[RedactionDecisionItem]


class RedactionDecisionResponse(BaseModel):
    id: int
    text_original: str
    text_replacement: str
    pii_type: str
    detection_method: str
    confirmed: bool
    overridden: bool


class RedactionSummaryResponse(BaseModel):
    applied: int    # spans confirmed and queued for redaction
    skipped: int    # spans overridden (kept as-is)
    status: str     # "ingestion_queued" | "ingestion_skipped"


class ProjectDocumentItem(BaseModel):
    id: str
    doc_type: Literal["uploaded", "generated"]
    filename: str
    status: str
    size_bytes: int | None
    created_at: str
    download_url: str
