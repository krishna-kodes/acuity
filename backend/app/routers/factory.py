from fastapi import APIRouter

router = APIRouter(tags=["factory"])


@router.post("/factory/seed-employees")
def seed_employees():
    pass


@router.post("/factory/seed-projects")
def seed_projects():
    pass


@router.post("/factory/seed-technologies")
def seed_technologies():
    pass


@router.post("/factory/seed-all")
def seed_all():
    pass


@router.delete("/factory/reset-db")
def reset_db():
    pass
