"""Tests for E5-T4: PII detection, Fernet encryption, redaction, ingest guards."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Regex detection
# ---------------------------------------------------------------------------

def test_regex_detects_email():
    from app.services.pii_detection import detect_pii

    spans = detect_pii("Contact alice@example.com for details.")
    emails = [s for s in spans if s.pii_type == "EMAIL"]
    assert len(emails) == 1
    assert emails[0].text == "alice@example.com"
    assert emails[0].method == "regex"
    assert emails[0].replacement == "[EMAIL_1]"


def test_regex_detects_phone():
    from app.services.pii_detection import detect_pii

    spans = detect_pii("Call us at (555) 123-4567 any time.")
    phones = [s for s in spans if s.pii_type == "PHONE"]
    assert len(phones) >= 1
    assert phones[0].method == "regex"


def test_regex_detects_ssn():
    from app.services.pii_detection import detect_pii

    spans = detect_pii("SSN: 123-45-6789 is confidential.")
    ssns = [s for s in spans if s.pii_type == "SSN"]
    assert len(ssns) == 1
    assert ssns[0].text == "123-45-6789"
    assert ssns[0].method == "regex"


def test_regex_detects_multiple_emails_with_sequential_tokens():
    from app.services.pii_detection import detect_pii

    spans = detect_pii("Email a@b.com and c@d.com for info.")
    emails = [s for s in spans if s.pii_type == "EMAIL"]
    assert len(emails) == 2
    replacements = {s.replacement for s in emails}
    assert "[EMAIL_1]" in replacements
    assert "[EMAIL_2]" in replacements


def test_pii_detection_disabled_returns_empty():
    from app.services.pii_detection import detect_pii

    with patch("app.services.pii_detection.settings") as mock_settings:
        mock_settings.pii_detection_enabled = False
        mock_settings.pii_regex_enabled = True
        mock_settings.pii_ner_enabled = True
        result = detect_pii("alice@example.com")

    assert result == []


# ---------------------------------------------------------------------------
# NER detection
# ---------------------------------------------------------------------------

def test_ner_skips_when_disabled():
    from app.services.pii_detection import detect_pii

    with patch("app.services.pii_detection.settings") as mock_settings:
        mock_settings.pii_detection_enabled = True
        mock_settings.pii_regex_enabled = False
        mock_settings.pii_ner_enabled = False
        result = detect_pii("John Smith is the lead engineer.")

    assert result == []


def test_ner_skips_gracefully_when_spacy_missing():
    from app.services.pii_detection import _detect_ner

    with patch("builtins.__import__", side_effect=ImportError("no spacy")):
        result = _detect_ner("John Smith works here.")

    assert result == []


# ---------------------------------------------------------------------------
# Redaction
# ---------------------------------------------------------------------------

def test_apply_redactions_replaces_single_span():
    from app.services.pii_detection import PIISpan, apply_redactions

    text = "Email alice@example.com now."
    spans = [PIISpan("alice@example.com", "[EMAIL_1]", "EMAIL", "regex", 6, 23)]
    result = apply_redactions(text, spans)
    assert result == "Email [EMAIL_1] now."
    assert "alice@example.com" not in result


def test_apply_redactions_handles_multiple_spans():
    from app.services.pii_detection import PIISpan, apply_redactions

    text = "alice@a.com and bob@b.com"
    spans = [
        PIISpan("alice@a.com", "[EMAIL_1]", "EMAIL", "regex", 0, 11),
        PIISpan("bob@b.com", "[EMAIL_2]", "EMAIL", "regex", 16, 25),
    ]
    result = apply_redactions(text, spans)
    assert "[EMAIL_1]" in result
    assert "[EMAIL_2]" in result
    assert "alice" not in result
    assert "bob" not in result


def test_apply_redactions_empty_spans_returns_original():
    from app.services.pii_detection import apply_redactions

    text = "No PII here."
    assert apply_redactions(text, []) == text


# ---------------------------------------------------------------------------
# Fernet encryption
# ---------------------------------------------------------------------------

def test_encrypt_roundtrip():
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    with patch("app.services.pii_detection.settings") as mock_settings:
        mock_settings.pii_encryption_key = key

        from app.services.pii_detection import decrypt_original, encrypt_original

        ciphertext = encrypt_original("alice@example.com")
        assert ciphertext != "alice@example.com"
        assert decrypt_original(ciphertext) == "alice@example.com"


def test_encrypt_returns_plaintext_without_key():
    from app.services.pii_detection import encrypt_original

    with patch("app.services.pii_detection.settings") as mock_settings:
        mock_settings.pii_encryption_key = ""
        result = encrypt_original("alice@example.com")

    assert result == "alice@example.com"


# ---------------------------------------------------------------------------
# detect_and_stage_pii integration (mocked DB)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_detect_and_stage_pii_stores_detections(tmp_path):
    """detect_and_stage_pii creates PIIDetection rows and sets status=anonymising."""
    from app.services.ingestion import detect_and_stage_pii

    text = "Contact alice@example.com for help."
    file_path = str(tmp_path / "doc.pdf")
    mock_db = MagicMock()

    # chromadb is not installed in test env — stub out the embedder module entirely
    mock_embedder = MagicMock()
    mock_embedder.collection_exists.return_value = False

    from app.services.pii_detection import PIISpan

    with (
        patch.dict("sys.modules", {"app.services.embedder": mock_embedder}),
        patch("app.services.ingestion._parse") as mock_parse,
        patch("app.services.ingestion.settings") as mock_settings,
        patch("app.services.pii_detection.detect_pii") as mock_detect,
        patch("app.services.pii_detection.encrypt_original", side_effect=lambda x: x),
    ):
        mock_settings.pii_detection_enabled = True
        mock_settings.pii_review_gate = True

        mock_page = MagicMock()
        mock_page.text = text
        parsed = MagicMock()
        parsed.pages = [mock_page]
        mock_parse.return_value = parsed

        mock_detect.return_value = [
            PIISpan("alice@example.com", "[EMAIL_1]", "EMAIL", "regex", 8, 25)
        ]

        count = await detect_and_stage_pii(1, 42, file_path, mock_db)

    assert count == 1
    mock_db.add.assert_called()
    mock_db.commit.assert_called()


@pytest.mark.asyncio
async def test_detect_and_stage_pii_skips_detection_when_disabled(tmp_path):
    from app.services.ingestion import detect_and_stage_pii

    file_path = str(tmp_path / "doc.pdf")
    mock_db = MagicMock()

    mock_embedder = MagicMock()
    mock_embedder.collection_exists.return_value = False

    with (
        patch.dict("sys.modules", {"app.services.embedder": mock_embedder}),
        patch("app.services.ingestion._parse") as mock_parse,
        patch("app.services.ingestion.settings") as mock_settings,
        patch("app.services.ingestion._chunk_and_embed", new_callable=AsyncMock) as mock_embed,
    ):
        mock_settings.pii_detection_enabled = False

        mock_page = MagicMock()
        mock_page.text = "clean text"
        parsed = MagicMock()
        parsed.pages = [mock_page]
        mock_parse.return_value = parsed
        mock_embed.return_value = 2

        count = await detect_and_stage_pii(1, 42, file_path, mock_db)

    assert count == 0
    mock_embed.assert_awaited_once()


# ---------------------------------------------------------------------------
# Redaction endpoints (router)
# ---------------------------------------------------------------------------

def test_get_redaction_decisions_returns_empty_for_unknown_project(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db

    def override_db():
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.all.return_value = []
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        resp = client.get("/api/v1/projects/999/redaction-decisions")
        assert resp.status_code == 200
        assert resp.json() == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_patch_redaction_decisions_updates_detections(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_db
    from app.models.pii import PIIDetection

    mock_det = MagicMock(spec=PIIDetection)
    mock_det.id = 1
    mock_det.confirmed = False
    mock_det.overridden = False

    def override_db():
        mock_db = MagicMock()

        def query_side_effect(model):
            q = MagicMock()
            q.filter.return_value = q
            if model is PIIDetection:
                q.first.return_value = mock_det
                q.all.return_value = []
            else:
                # Document query
                q.first.return_value = None
            return q

        mock_db.query.side_effect = query_side_effect
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        resp = client.patch(
            "/api/v1/projects/1/redaction-decisions",
            json={"decisions": [{"detection_id": 1, "confirmed": True}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["applied"] == 1
        assert body["skipped"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
