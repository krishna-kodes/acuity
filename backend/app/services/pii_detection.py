"""PII detection and encryption for ingested documents.

Two-pass detection per ADR-006:
  1. Regex pass (PII_REGEX_ENABLED) — structured patterns: email, phone, SSN
  2. spaCy NER pass (PII_NER_ENABLED) — contextual entities: PERSON, ORG, GPE

Detected spans are stored in pii_detections with the original text Fernet-encrypted
(PII_ENCRYPTION_KEY). Replacement tokens like [EMAIL_1] are used in the anonymised text.

If PII_REVIEW_GATE=True the document waits in `anonymising` status until the PM
confirms or overrides each detection via PATCH /redaction-decisions.
"""

import re
from dataclasses import dataclass, field

from app.config import settings


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_REGEX_PATTERNS: dict[str, re.Pattern] = {
    "EMAIL": re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b"),
    "PHONE": re.compile(
        r"(\+?1[\s\-]?)?(\([0-9]{3}\)|[0-9]{3})[\s.\-][0-9]{3}[\s.\-][0-9]{4}"
    ),
    "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
}

_NER_LABELS: frozenset[str] = frozenset({"PERSON", "ORG", "GPE"})


# ---------------------------------------------------------------------------
# PIISpan dataclass
# ---------------------------------------------------------------------------

@dataclass
class PIISpan:
    text: str          # original text (e.g. "alice@example.com")
    replacement: str   # token inserted in anonymised text (e.g. "[EMAIL_1]")
    pii_type: str      # "EMAIL", "PHONE", "SSN", "PERSON", "ORG", "GPE"
    method: str        # "regex" | "ner"
    start: int         # char offset in source text
    end: int           # char offset in source text


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _detect_regex(text: str) -> list[PIISpan]:
    spans: list[PIISpan] = []
    counters: dict[str, int] = {}
    for pii_type, pattern in _REGEX_PATTERNS.items():
        for match in pattern.finditer(text):
            counters[pii_type] = counters.get(pii_type, 0) + 1
            spans.append(
                PIISpan(
                    text=match.group(),
                    replacement=f"[{pii_type}_{counters[pii_type]}]",
                    pii_type=pii_type,
                    method="regex",
                    start=match.start(),
                    end=match.end(),
                )
            )
    return spans


def _detect_ner(text: str) -> list[PIISpan]:
    try:
        import spacy  # type: ignore[import-untyped]

        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            return []
    except ImportError:
        return []

    doc = nlp(text)
    spans: list[PIISpan] = []
    counters: dict[str, int] = {}
    for ent in doc.ents:
        if ent.label_ not in _NER_LABELS:
            continue
        counters[ent.label_] = counters.get(ent.label_, 0) + 1
        spans.append(
            PIISpan(
                text=ent.text,
                replacement=f"[{ent.label_}_{counters[ent.label_]}]",
                pii_type=ent.label_,
                method="ner",
                start=ent.start_char,
                end=ent.end_char,
            )
        )
    return spans


def _remove_overlaps(spans: list[PIISpan]) -> list[PIISpan]:
    """Keep the earliest span when two spans overlap; prefer regex over NER."""
    sorted_spans = sorted(spans, key=lambda s: (s.start, s.method != "regex"))
    kept: list[PIISpan] = []
    last_end = -1
    for span in sorted_spans:
        if span.start >= last_end:
            kept.append(span)
            last_end = span.end
    return kept


def detect_pii(text: str) -> list[PIISpan]:
    """Two-pass PII detection. Respects PII_REGEX_ENABLED and PII_NER_ENABLED.

    Returns a deduplicated, non-overlapping list of PIISpan sorted by start offset.
    """
    if not settings.pii_detection_enabled:
        return []

    spans: list[PIISpan] = []

    if settings.pii_regex_enabled:
        spans.extend(_detect_regex(text))

    if settings.pii_ner_enabled:
        spans.extend(_detect_ner(text))

    return _remove_overlaps(spans)


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

def encrypt_original(text: str) -> str:
    """Fernet-encrypt the original PII text for storage (ADR-006).

    Returns the ciphertext as a base64 string, or the original text if
    PII_ENCRYPTION_KEY is not configured (test / dev without key).
    """
    key = settings.pii_encryption_key
    if not key:
        return text

    from cryptography.fernet import Fernet

    f = Fernet(key.encode())
    return f.encrypt(text.encode()).decode()


def decrypt_original(ciphertext: str) -> str:
    """Fernet-decrypt a stored PII original. Returns ciphertext if no key set."""
    key = settings.pii_encryption_key
    if not key:
        return ciphertext

    from cryptography.fernet import Fernet

    f = Fernet(key.encode())
    return f.decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def apply_redactions(text: str, spans: list[PIISpan]) -> str:
    """Replace all span texts with their replacement tokens.

    Processes spans in descending start-offset order so earlier replacements
    do not shift the character positions of later ones.
    """
    sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)
    for span in sorted_spans:
        text = text[: span.start] + span.replacement + text[span.end :]
    return text
