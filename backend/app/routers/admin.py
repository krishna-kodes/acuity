from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.branding import BrandingSettings
from app.models.employee import Employee, EmployeeSkill, Skill
from app.schemas.branding import BrandingSettingsResponse, BrandingSettingsUpdate
from app.services.branding import get_branding

router = APIRouter(prefix="/admin", tags=["admin"])


class SkillOut(BaseModel):
    id: int
    name: str
    category: str
    model_config = {"from_attributes": True}


class EmployeeOut(BaseModel):
    id: int
    name: str
    email: str | None
    seniority: str
    availability_pct: int
    joined_at: str | None
    status: str
    skills: list[SkillOut]


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(db: Session = Depends(get_db)) -> list[EmployeeOut]:
    """List all employees with their skills."""
    emps = (
        db.query(Employee)
        .options(joinedload(Employee.employee_skills).joinedload(EmployeeSkill.skill))
        .order_by(Employee.name)
        .all()
    )
    return [
        EmployeeOut(
            id=e.id,
            name=e.name,
            email=e.email,
            seniority=e.seniority,
            availability_pct=e.availability_pct,
            joined_at=e.joined_at.isoformat() if e.joined_at else None,
            status=e.status,
            skills=[
                SkillOut(id=es.skill.id, name=es.skill.name, category=es.skill.category)
                for es in e.employee_skills
            ],
        )
        for e in emps
    ]


@router.get("/skills", response_model=list[SkillOut])
def list_skills(db: Session = Depends(get_db)) -> list[SkillOut]:
    """List all skills ordered by category then name."""
    return db.query(Skill).order_by(Skill.category, Skill.name).all()


@router.get("/branding", response_model=BrandingSettingsResponse)
def get_branding_settings(db: Session = Depends(get_db)) -> BrandingSettingsResponse:
    """Return current branding settings (DB row merged with env defaults)."""
    return get_branding(db)


@router.put("/branding", response_model=BrandingSettingsResponse)
def update_branding_settings(
    body: BrandingSettingsUpdate, db: Session = Depends(get_db)
) -> BrandingSettingsResponse:
    """Upsert branding settings (partial update — only provided fields are changed)."""
    row = db.query(BrandingSettings).filter(BrandingSettings.id == 1).first()
    if row is None:
        # Seed new row from current merged values so partial PUT doesn't
        # stomp env-var defaults with model defaults for un-provided fields.
        current = get_branding(db)
        row = BrandingSettings(
            id=1,
            company_name=current.company_name,
            primary_color=current.primary_color,
            secondary_color=current.secondary_color,
            prepared_by=current.prepared_by,
            updated_at=datetime.utcnow(),
        )
        db.add(row)

    if body.company_name is not None:
        row.company_name = body.company_name
    if body.primary_color is not None:
        row.primary_color = body.primary_color
    if body.secondary_color is not None:
        row.secondary_color = body.secondary_color
    if body.prepared_by is not None:
        row.prepared_by = body.prepared_by
    row.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(row)
    return get_branding(db)


@router.delete("/branding", status_code=204)
def reset_branding_settings(db: Session = Depends(get_db)) -> None:
    """Delete the DB branding row — GET will fall back to env/hardcoded defaults."""
    row = db.query(BrandingSettings).filter(BrandingSettings.id == 1).first()
    if row:
        db.delete(row)
        db.commit()
