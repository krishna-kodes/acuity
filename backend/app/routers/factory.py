from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.sync import SeedResult

router = APIRouter(tags=["factory"])

_RESET_ORDER = [
    "pii_ingestion_logs", "pii_detections",
    "error_logs", "latency_logs", "metrics",
    "tasks", "epics",
    "proposals", "clarifications", "documents",
    "historical_projects", "approved_technologies",
    "employee_skills", "skills", "employees",
    "proposal_state", "projects",
]


@router.post("/factory/seed-employees", response_model=SeedResult)
def seed_employees(db: Session = Depends(get_db)) -> SeedResult:
    from app.services.seeder import seed_employees as _seed
    seeded = _seed(db)
    return SeedResult(seeded=seeded, status="ok")


@router.post("/factory/seed-projects", response_model=SeedResult)
def seed_projects(db: Session = Depends(get_db)) -> SeedResult:
    from app.services.seeder import seed_projects as _seed
    seeded = _seed(db)
    return SeedResult(seeded=seeded, status="ok")


@router.post("/factory/seed-technologies", response_model=SeedResult)
def seed_technologies(db: Session = Depends(get_db)) -> SeedResult:
    from app.services.seeder import seed_technologies as _seed
    seeded = _seed(db)
    return SeedResult(seeded=seeded, status="ok")


@router.post("/factory/seed-all", response_model=SeedResult)
def seed_all(db: Session = Depends(get_db)) -> SeedResult:
    from app.services.seeder import seed_employees, seed_projects, seed_technologies
    total = seed_employees(db) + seed_projects(db) + seed_technologies(db)
    return SeedResult(seeded=total, status="ok")


def _wipe_vector_store() -> int:
    """Drop every ChromaDB collection. Returns count deleted.

    Without this, collections orphan when app.db is reset — a stale
    project URL keeps retrieving the old document's embeddings.
    """
    import chromadb

    from app.config import settings

    client = chromadb.PersistentClient(path=settings.chroma_persist_path)
    names = [c.name for c in client.list_collections()]
    for name in names:
        try:
            client.delete_collection(name)
        except Exception:
            pass
    return len(names)


def _wipe_checkpointer() -> None:
    """Clear LangGraph checkpointer threads so chat history can't replay
    a previous document's conversation after a reset."""
    import sqlite3

    try:
        con = sqlite3.connect("./project_state.db")
        for tbl in ("writes", "checkpoints"):
            try:
                con.execute(f"DELETE FROM {tbl}")
            except Exception:
                pass
        con.commit()
        con.close()
    except Exception:
        pass


@router.delete("/factory/reset-db")
def reset_db(db: Session = Depends(get_db)) -> dict:
    for table in _RESET_ORDER:
        try:
            db.execute(text(f"DELETE FROM {table}"))
        except Exception:
            pass
    db.commit()
    collections_dropped = _wipe_vector_store()
    _wipe_checkpointer()
    return {"status": "reset", "collections_dropped": collections_dropped}
