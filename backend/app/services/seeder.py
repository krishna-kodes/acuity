"""Faker-based seed data for employees, historical projects, and approved technologies."""

from faker import Faker
from sqlalchemy.orm import Session

from app.config import settings
from app.models.employee import Employee, EmployeeSkill, Skill
from app.models.reference import ApprovedTechnology, HistoricalProject

_SENIORITY_LEVELS = ["Junior", "Mid", "Senior", "Lead", "Principal"]
_DOMAINS = ["fintech", "healthtech", "edtech", "ecommerce", "logistics", "saas", "iot"]

_SEED_SKILLS = [
    ("Python", "programming"), ("JavaScript", "programming"), ("TypeScript", "programming"),
    ("Go", "programming"), ("Rust", "programming"), ("Java", "programming"),
    ("React", "framework"), ("Next.js", "framework"), ("FastAPI", "framework"),
    ("Django", "framework"), ("Node.js", "framework"),
    ("PostgreSQL", "database"), ("SQLite", "database"), ("MongoDB", "database"),
    ("Redis", "database"), ("Docker", "devops"), ("Kubernetes", "devops"),
    ("AWS", "devops"), ("Figma", "design"), ("SQL", "database"),
]

_APPROVED_TECHS = [
    ("Next.js", "frontend"), ("React", "frontend"), ("Vue.js", "frontend"),
    ("TypeScript", "frontend"), ("Tailwind CSS", "frontend"),
    ("FastAPI", "backend"), ("Django", "backend"), ("Node.js", "backend"),
    ("Go", "backend"), ("Rust", "backend"),
    ("PostgreSQL", "database"), ("SQLite", "database"), ("MongoDB", "database"),
    ("Redis", "database"), ("Elasticsearch", "database"),
    ("Docker", "infra"), ("Kubernetes", "infra"), ("Railway", "infra"),
    ("AWS Lambda", "infra"), ("Terraform", "infra"),
    ("LangChain", "ai"), ("ChromaDB", "ai"),
]


def _ensure_skills(db: Session, fake: Faker) -> list[Skill]:
    existing = db.query(Skill).all()
    if existing:
        return existing
    skills = []
    for name, cat in _SEED_SKILLS:
        skill = Skill(name=name, category=cat)
        db.add(skill)
        skills.append(skill)
    db.flush()
    return skills


def seed_employees(db: Session, count: int | None = None) -> int:
    if count is None:
        count = settings.seed_employee_count
    fake = Faker()
    fake.seed_instance(settings.faker_seed)
    skills = _ensure_skills(db, fake)
    seeded = 0
    for _ in range(count):
        emp = Employee(
            name=fake.name(),
            email=fake.unique.email(),
            seniority=fake.random_element(_SENIORITY_LEVELS),
            availability_pct=fake.random_element([50, 75, 100]),
        )
        db.add(emp)
        db.flush()
        num = fake.random_int(min=2, max=5)
        chosen = fake.random_elements(skills, length=min(num, len(skills)), unique=True)
        for skill in chosen:
            db.add(EmployeeSkill(employee_id=emp.id, skill_id=skill.id))
        seeded += 1
    db.commit()
    return seeded


def seed_projects(db: Session, count: int | None = None) -> int:
    if count is None:
        count = settings.seed_project_count
    fake = Faker()
    fake.seed_instance(settings.faker_seed)
    seeded = 0
    for _ in range(count):
        db.add(HistoricalProject(
            name=fake.bs().title(),
            domain=fake.random_element(_DOMAINS),
            estimated_points=fake.random_int(min=20, max=150),
            actual_points=fake.random_int(min=20, max=200),
            duration_weeks=round(fake.pyfloat(min_value=2.0, max_value=24.0, right_digits=1), 1),
            team_size=fake.random_int(min=2, max=10),
        ))
        seeded += 1
    db.commit()
    return seeded


def seed_technologies(db: Session, count: int | None = None) -> int:
    if count is None:
        count = settings.seed_technology_count
    seeded = 0
    for name, category in _APPROVED_TECHS[:count]:
        if db.query(ApprovedTechnology).filter(ApprovedTechnology.name == name).first():
            continue
        db.add(ApprovedTechnology(name=name, category=category))
        seeded += 1
    db.commit()
    return seeded
