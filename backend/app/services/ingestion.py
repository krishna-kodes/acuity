"""Document ingestion pipeline.

Phase 1a — detect_and_stage_pii():
  Parse → detect PII → store pii_detections → set status=anonymising.
  If PII_DETECTION_ENABLED=False or PII_REVIEW_GATE=False, falls through
  directly to Phase 1b.

Phase 1b — complete_ingestion():
  Load confirmed/overridden decisions → apply redactions → chunk → embed → status=ready.
  Called automatically in Phase 1a when the review gate is disabled, or
  triggered via PATCH /redaction-decisions when the gate is enabled.

ingest_document() is a backward-compatible wrapper for callers that ran before
the PII gate was added (e.g. test_routes.py background task call).
"""

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import DocumentStatus, ProjectPhase
from app.models.project import Document, Project


@dataclass
class PageContent:
    page_number: int
    text: str
    tables: list[list[list[str]]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    filename: str
    pages: list[PageContent]


@dataclass
class Chunk:
    text: str
    chunk_index: int
    project_id: str
    detected_type: str   # "paragraph" | "header" | "table" | "list_item"
    page_number: int
    section_hint: str
    token_count: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _parse(file_path: str) -> ParsedDocument:
    from app.services.parser import parse_docx, parse_pdf

    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return await parse_pdf(file_path)
    if ext in (".docx", ".doc"):
        return await parse_docx(file_path)
    raise ValueError(f"Unsupported file type: {ext}")


async def _chunk_and_embed(
    document_id: int,
    project_id: int,
    parsed: ParsedDocument,
    db: Session,
    *,
    redacted_text: str | None = None,
) -> int:
    """Chunk, embed, and mark document ready. Returns chunk count."""
    from app.services.chunker import chunk_document
    from app.services.embedder import embed_and_store

    chroma_project_id = str(project_id)

    anonymized_path: str | None = None
    if redacted_text is not None:
        # Replace parsed text with the redacted version
        for page in parsed.pages:
            page.text = redacted_text
        # Persist the redacted text so the chat-page preview can serve it
        # without reconstructing from ChromaDB chunks.
        import os as _os

        _os.makedirs("documents", exist_ok=True)
        anonymized_path = f"documents/{project_id}_{document_id}_redacted.txt"
        try:
            with open(anonymized_path, "w", encoding="utf-8") as _f:
                _f.write(redacted_text)
        except OSError:
            anonymized_path = None

    chunks = await chunk_document(
        parsed,
        chroma_project_id,
        min_tokens=settings.chunk_size_min_tokens,
        max_tokens=settings.chunk_size_max_tokens,
    )

    if settings.prompt_injection_detection_enabled:
        from app.guardrails import log_guardrail as _log_guardrail
        from app.guardrails.prompt_injection import scan as _inj_scan
        flagged = [c for c in chunks if _inj_scan(c.text).detected]
        if flagged:
            _log_guardrail(
                str(project_id), 1, "injection_in_document", None,
                {"flagged_chunks": len(flagged), "total_chunks": len(chunks)},
            )

    stored = await embed_and_store(chunks)

    _doc_update: dict = {"status": DocumentStatus.ready}
    if anonymized_path is not None:
        _doc_update["anonymized_path"] = anonymized_path
    db.query(Document).filter(Document.id == document_id).update(_doc_update)
    db.query(Project).filter(Project.id == project_id).update(
        {"phase": ProjectPhase.chat}
    )
    db.commit()
    return stored


# ---------------------------------------------------------------------------
# Phase 1a: PII detection + staging
# ---------------------------------------------------------------------------

async def detect_and_stage_pii(
    document_id: int,
    project_id: int,
    file_path: str,
    db: Session,
) -> int:
    """Parse document, detect PII, store detections, set status=anonymising.

    Returns the number of PII spans detected.

    If pii_detection_enabled=False → skips detection, proceeds to complete_ingestion.
    If pii_review_gate=False → auto-confirms all detections and proceeds.
    If pii_review_gate=True → stops here; PM must call complete_ingestion() after review.
    """
    from app.services.embedder import collection_exists, delete_collection, get_collection

    chroma_project_id = str(project_id)

    # Only use ChromaDB cache if SQLite state is also complete (status=ready).
    # If ChromaDB exists but document isn't ready, a prior run was interrupted —
    # drop the stale collection and re-run PII detection.
    if collection_exists(chroma_project_id):
        doc_status = db.query(Document).filter(Document.id == document_id).first()
        if doc_status and doc_status.status == DocumentStatus.ready:
            return get_collection(chroma_project_id).count()
        delete_collection(chroma_project_id)

    from app.models.pii import PIIDetection
    existing = db.query(PIIDetection).filter(
        PIIDetection.document_id == document_id
    ).count()
    if existing > 0:
        return existing

    parsed = await _parse(file_path)

    # Concatenate all page text for PII scanning
    full_text = "\n".join(page.text for page in parsed.pages)

    if not settings.pii_detection_enabled:
        await _chunk_and_embed(document_id, project_id, parsed, db)
        return 0

    from app.models.pii import PIIDetection, PIIIngestionLog
    from app.services.pii_detection import (
        detect_pii,
        encrypt_original,
        filter_ner_candidates_llm,
    )

    spans = detect_pii(full_text)

    # P2: LLM quality filter — pre-prune NER false positives before review so
    # garbage entities never reach the PM. PM can still Undo any pruned item.
    ner_keep: set[str] = set()
    if settings.pii_auto_llm_filter:
        ner_texts = list({s.text for s in spans if s.method == "ner"})
        if ner_texts:
            ner_keep = set(await filter_ner_candidates_llm(ner_texts, str(project_id)))

    # Persist detections
    pruned_count = 0
    for span in spans:
        is_pruned = (
            settings.pii_auto_llm_filter
            and span.method == "ner"
            and span.text not in ner_keep
        )
        if is_pruned:
            pruned_count += 1
        detection = PIIDetection(
            document_id=document_id,
            text_original=encrypt_original(span.text),
            text_replacement=span.replacement,
            pii_type=span.pii_type,
            detection_method=span.method,
            confirmed=False,
            overridden=is_pruned,
        )
        db.add(detection)

    log = PIIIngestionLog(
        project_id=project_id,
        document_id=document_id,
        event="pii_detected",
        detail=f"{len(spans)} spans detected, {pruned_count} NER false positives auto-pruned",
    )
    db.add(log)

    db.query(Document).filter(Document.id == document_id).update(
        {"status": DocumentStatus.anonymising}
    )
    db.commit()

    if not settings.pii_review_gate:
        # Auto-confirm all: proceed immediately
        await complete_ingestion(document_id, project_id, db)

    return len(spans)


# ---------------------------------------------------------------------------
# Phase 1b: Complete ingestion after redaction review
# ---------------------------------------------------------------------------

async def complete_ingestion(
    document_id: int,
    project_id: int,
    db: Session,
) -> int:
    """Apply PM redaction decisions, then chunk + embed. Returns chunk count.

    For each PIIDetection row:
    - confirmed=True  → replace original text with token in document
    - overridden=True → keep original text unchanged
    - neither set     → treat as auto-confirmed
    """
    from app.models.pii import PIIDetection
    from app.services.pii_detection import PIISpan, apply_redactions, decrypt_original

    parsed = None

    # Load document record to find file_path
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        raise ValueError(f"Document {document_id} not found")

    # Rebuild file_path from the document record
    file_path = f"documents/{doc.project_id}_{doc.filename}"
    parsed = await _parse(file_path)
    full_text = "\n".join(page.text for page in parsed.pages)

    # Build span list from stored detections (only confirmed, not overridden)
    detections = (
        db.query(PIIDetection)
        .filter(PIIDetection.document_id == document_id, PIIDetection.overridden.is_(False))
        .all()
    )

    spans_to_apply: list[PIISpan] = []
    for det in detections:
        original = decrypt_original(det.text_original)
        # Find the span position in text
        idx = full_text.find(original)
        if idx == -1:
            continue
        spans_to_apply.append(
            PIISpan(
                text=original,
                replacement=det.text_replacement,
                pii_type=det.pii_type,
                method=det.detection_method,
                start=idx,
                end=idx + len(original),
            )
        )

    redacted_text = apply_redactions(full_text, spans_to_apply) if spans_to_apply else full_text

    return await _chunk_and_embed(document_id, project_id, parsed, db, redacted_text=redacted_text)


# ---------------------------------------------------------------------------
# Backward-compatible wrapper
# ---------------------------------------------------------------------------

async def ingest_document(
    document_id: int,
    project_id: int,
    file_path: str,
    db: Session,
) -> int:
    """Parse, detect PII, chunk, embed, and store a document. Returns chunk count.

    Re-ingestion of the same project_id is a no-op (cache hit via ChromaDB).
    Delegates to detect_and_stage_pii() which handles the PII gate.
    """
    return await detect_and_stage_pii(document_id, project_id, file_path, db)
