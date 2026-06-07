from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    employee_skills: Mapped[list["EmployeeSkill"]] = relationship(back_populates="skill")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    seniority: Mapped[str] = mapped_column(String(50), nullable=False)
    availability_pct: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    employee_skills: Mapped[list["EmployeeSkill"]] = relationship(back_populates="employee")


class EmployeeSkill(Base):
    __tablename__ = "employee_skills"
    __table_args__ = (
        UniqueConstraint("employee_id", "skill_id"),
        Index("ix_employee_skills_employee_id", "employee_id"),
        Index("ix_employee_skills_skill_id", "skill_id"),
    )

    employee_id: Mapped[int] = mapped_column(Integer, ForeignKey("employees.id"), primary_key=True)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"), primary_key=True)

    employee: Mapped["Employee"] = relationship(back_populates="employee_skills")
    skill: Mapped["Skill"] = relationship(back_populates="employee_skills")
