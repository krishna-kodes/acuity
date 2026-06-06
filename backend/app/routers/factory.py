from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.sync import SeedResult

router = APIRouter(tags=["factory"])


@router.post("/factory/seed-employees", response_model=SeedResult)
def seed_employees(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-projects", response_model=SeedResult)
def seed_projects(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-technologies", response_model=SeedResult)
def seed_technologies(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed from Faker with FAKER_SEED
    return SeedResult(seeded=0, status="ok")


@router.post("/factory/seed-all", response_model=SeedResult)
def seed_all(db: Session = Depends(get_db)) -> SeedResult:
    # TODO(Epic 5 #40): seed all tables
    return SeedResult(seeded=0, status="ok")


@router.delete("/factory/reset-db")
def reset_db(db: Session = Depends(get_db)) -> dict:
    # TODO(Epic 5 #35): drop and recreate all tables
    return {"status": "reset"}
