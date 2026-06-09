from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, field_validator

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validate_hex(v: str | None) -> str | None:
    if v is None:
        return v
    if not _HEX_RE.match(v):
        raise ValueError(f"Color must be #RRGGBB hex format, got: {v!r}")
    return v


class BrandingSettingsResponse(BaseModel):
    company_name: str
    primary_color: str
    secondary_color: str
    prepared_by: str
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class BrandingSettingsUpdate(BaseModel):
    company_name: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    prepared_by: str | None = None

    @field_validator("primary_color", "secondary_color", mode="before")
    @classmethod
    def validate_hex(cls, v: str | None) -> str | None:
        return _validate_hex(v)
