"""Seed reference data directly via a DB session — no running server needed.

Seeds employees, historical projects, and approved technologies. These are
reference/calibration tables (not user projects, which are created by
uploading documents in the UI).

Usage (run from backend/):
    python scripts/seed_offline.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.services.seeder import seed_employees, seed_projects, seed_technologies


def main() -> int:
    db = SessionLocal()
    try:
        emp = seed_employees(db)
        proj = seed_projects(db)       # historical_projects (estimation reference)
        tech = seed_technologies(db)
        print(f"seeded: {emp} employees, {proj} historical projects, {tech} technologies")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
