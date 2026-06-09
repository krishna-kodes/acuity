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
    # (name, category, tags)
    ("Next.js",       "frontend", "SPA,SSR,TypeScript-first,prototyping,production"),
    ("React",         "frontend", "SPA,component-library,flexible,prototyping,production"),
    ("Vue.js",        "frontend", "SPA,lightweight,progressive,prototyping"),
    ("TypeScript",    "frontend", "typed,compile-time-safety,large-team"),
    ("Tailwind CSS",  "frontend", "utility-CSS,rapid-prototyping,design-system"),
    ("FastAPI",       "backend",  "REST,async,Python,ML-friendly,prototyping,production"),
    ("Django",        "backend",  "REST,batteries-included,ORM,Python,high-scale"),
    ("Node.js",       "backend",  "REST,event-driven,JavaScript,high-scale"),
    ("Go",            "backend",  "REST,high-performance,compiled,high-scale"),
    ("Rust",          "backend",  "systems,high-performance,compiled,high-scale"),
    ("PostgreSQL",    "database", "relational,ACID,production,high-scale"),
    ("SQLite",        "database", "relational,embedded,prototyping,low-scale"),
    ("MongoDB",       "database", "NoSQL,flexible-schema,document-store,high-scale"),
    ("Redis",         "database", "cache,pub-sub,session-store,high-scale"),
    ("Elasticsearch", "database", "search,full-text,analytics,high-scale"),
    ("Docker",        "infra",    "containerization,local-dev,portable"),
    ("Kubernetes",    "infra",    "orchestration,high-scale,complex-ops,production"),
    ("Railway",       "infra",    "PaaS,simple-deploy,low-ops,prototyping"),
    ("AWS Lambda",    "infra",    "serverless,event-driven,high-scale,pay-per-use"),
    ("Terraform",     "infra",    "IaC,cloud-provisioning,production"),
    ("LangChain",     "ai",       "LLM-orchestration,RAG,agents,Python"),
    ("ChromaDB",      "ai",       "vector-store,embeddings,RAG,local-dev"),
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
            joined_at=fake.date_time_between(start_date="-3y", end_date="now"),
            status=fake.random_element(["active"] * 17 + ["inactive"] * 3),
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
    for name, category, tags in _APPROVED_TECHS[:count]:
        existing = db.query(ApprovedTechnology).filter(ApprovedTechnology.name == name).first()
        if existing:
            existing.tags = tags
        else:
            db.add(ApprovedTechnology(name=name, category=category, tags=tags))
        seeded += 1
    db.commit()
    return seeded
