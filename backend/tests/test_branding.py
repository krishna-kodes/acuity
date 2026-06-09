import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models as _models  # noqa: F401 — registers all ORM models
from app.models.base import Base
from app.models.branding import BrandingSettings
from app.services.branding import get_branding
from app.config import settings


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
