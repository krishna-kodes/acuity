from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.employee import Employee, EmployeeSkill, Skill

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
