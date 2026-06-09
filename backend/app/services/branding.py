from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import settings
from app.models.branding import BrandingSettings
from app.schemas.branding import BrandingSettingsResponse


def get_branding(db: Session) -> BrandingSettingsResponse:
    """Return merged branding: DB row > env default > hardcoded fallback."""
    row = db.query(BrandingSettings).filter(BrandingSettings.id == 1).first()

    def _pick(db_val: str | None, env_val: str, fallback: str) -> str:
        if db_val and db_val.strip():
            return db_val
        if env_val and env_val.strip():
            return env_val
        return fallback

    return BrandingSettingsResponse(
        company_name=_pick(
            row.company_name if row else None,
            settings.branding_company_name,
            "",
        ),
        primary_color=_pick(
            row.primary_color if row else None,
            settings.branding_primary_color,
            "#2E5FA3",
        ),
        secondary_color=_pick(
            row.secondary_color if row else None,
            settings.branding_secondary_color,
            "#1A3A6B",
        ),
        prepared_by=_pick(
            row.prepared_by if row else None,
            settings.branding_prepared_by,
            "",
        ),
        updated_at=row.updated_at if row else None,
    )
