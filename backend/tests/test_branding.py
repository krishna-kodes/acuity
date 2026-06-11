from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa: F401 — registers all ORM models
from app.config import settings
from app.models.base import Base
from app.models.branding import BrandingSettings
from app.services.branding import get_branding


@pytest.fixture
def mem_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_get_branding_returns_env_defaults_when_no_db_row(mem_db, monkeypatch):
    monkeypatch.setattr(settings, "branding_primary_color", "#AABBCC")
    monkeypatch.setattr(settings, "branding_company_name", "Env Corp")
    monkeypatch.setattr(settings, "branding_prepared_by", "")
    monkeypatch.setattr(settings, "branding_secondary_color", "#112233")

    result = get_branding(mem_db)

    assert result.primary_color == "#AABBCC"
    assert result.company_name == "Env Corp"
    assert result.secondary_color == "#112233"
    assert result.updated_at is None


def test_get_branding_returns_db_values_when_row_exists(mem_db, monkeypatch):
    monkeypatch.setattr(settings, "branding_primary_color", "#000000")

    row = BrandingSettings(
        id=1,
        company_name="DB Corp",
        primary_color="#FF0000",
        secondary_color="#00FF00",
        prepared_by="Alice",
        updated_at=datetime(2026, 6, 9),
    )
    mem_db.add(row)
    mem_db.commit()

    result = get_branding(mem_db)

    assert result.company_name == "DB Corp"
    assert result.primary_color == "#FF0000"
    assert result.secondary_color == "#00FF00"
    assert result.prepared_by == "Alice"
    assert result.updated_at == datetime(2026, 6, 9)


def test_get_branding_falls_back_to_hardcoded_when_env_empty(mem_db, monkeypatch):
    monkeypatch.setattr(settings, "branding_primary_color", "")
    monkeypatch.setattr(settings, "branding_secondary_color", "")
    monkeypatch.setattr(settings, "branding_company_name", "")
    monkeypatch.setattr(settings, "branding_prepared_by", "")

    result = get_branding(mem_db)

    assert result.primary_color == "#2E5FA3"
    assert result.secondary_color == "#1A3A6B"


from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app


@pytest.fixture
def api_client(mem_db):
    def override_db():
        yield mem_db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


def test_get_branding_endpoint_returns_200_with_defaults(api_client, monkeypatch):
    monkeypatch.setattr(settings, "branding_primary_color", "#2E5FA3")
    monkeypatch.setattr(settings, "branding_secondary_color", "#1A3A6B")
    monkeypatch.setattr(settings, "branding_company_name", "")
    monkeypatch.setattr(settings, "branding_prepared_by", "")

    resp = api_client.get("/api/v1/admin/branding")

    assert resp.status_code == 200
    data = resp.json()
    assert data["primary_color"] == "#2E5FA3"
    assert data["secondary_color"] == "#1A3A6B"
    assert "updated_at" in data


def test_put_branding_endpoint_updates_db(api_client):
    resp = api_client.put(
        "/api/v1/admin/branding",
        json={
            "company_name": "Acme Inc",
            "primary_color": "#FF5500",
            "secondary_color": "#003366",
            "prepared_by": "Bob Smith",
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "Acme Inc"
    assert data["primary_color"] == "#FF5500"
    assert data["prepared_by"] == "Bob Smith"


def test_put_branding_partial_update_only_changes_provided_fields(api_client, mem_db):
    row = BrandingSettings(
        id=1,
        company_name="Original Corp",
        primary_color="#111111",
        secondary_color="#222222",
        prepared_by="Alice",
        updated_at=datetime(2026, 6, 9),
    )
    mem_db.add(row)
    mem_db.commit()

    resp = api_client.put("/api/v1/admin/branding", json={"company_name": "New Corp"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["company_name"] == "New Corp"
    assert data["primary_color"] == "#111111"  # unchanged
    assert data["prepared_by"] == "Alice"  # unchanged


def test_put_branding_rejects_invalid_hex(api_client):
    resp = api_client.put(
        "/api/v1/admin/branding",
        json={"primary_color": "not-a-color"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Exporter tests
# ---------------------------------------------------------------------------

import os
from datetime import datetime as dt

from app.schemas.branding import BrandingSettingsResponse
from app.services.exporter import (
    ProposalContent,
    ProposalSection,
    _hex_to_rgb,
    generate_proposal_docx,
)


def test_hex_to_rgb_converts_correctly():
    rgb = _hex_to_rgb("#FF5500")
    assert rgb[0] == 0xFF
    assert rgb[1] == 0x55
    assert rgb[2] == 0x00


def test_hex_to_rgb_works_without_hash():
    rgb = _hex_to_rgb("2E5FA3")
    assert rgb[0] == 0x2E
    assert rgb[1] == 0x5F
    assert rgb[2] == 0xA3


def test_generate_proposal_docx_with_branding_does_not_raise(tmp_path):
    content = ProposalContent(
        title="Test Project",
        sections=[ProposalSection(heading="Overview", body="Some overview text.")],
    )
    branding = BrandingSettingsResponse(
        company_name="Acme Inc",
        primary_color="#FF5500",
        secondary_color="#003366",
        prepared_by="Alice",
        updated_at=dt(2026, 6, 9),
    )
    path = generate_proposal_docx(1, content, output_dir=str(tmp_path), branding=branding)
    assert os.path.exists(path)


def test_generate_proposal_docx_without_branding_unchanged(tmp_path):
    content = ProposalContent(
        title="No Brand",
        sections=[ProposalSection(heading="Section", body="Body text.")],
    )
    path = generate_proposal_docx(2, content, output_dir=str(tmp_path))
    assert os.path.exists(path)
