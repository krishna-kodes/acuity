"""Import real historical projects from a CSV — production estimation calibration.

The effort-estimation phase reads `historical_projects` as reference data
(`db.query(HistoricalProject).limit(10)`). In production, replace the Faker
seed with your organisation's real past projects via this importer.

CSV columns (header required):
    name,domain,estimated_points,actual_points,duration_weeks,team_size

- name is required and used as the upsert key (re-running updates, never duplicates)
- all other columns optional; blank cells become NULL
- numeric cells are coerced; bad values are reported and the row skipped

Usage (run from backend/):
    python scripts/import_historical.py path/to/projects.csv
    python scripts/import_historical.py path/to/projects.csv --replace   # truncate table first
"""
import argparse
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.reference import HistoricalProject

_INT_COLS = ("estimated_points", "actual_points", "team_size")
_FLOAT_COLS = ("duration_weeks",)
_FIELDS = ("name", "domain", *_INT_COLS, *_FLOAT_COLS)


def _coerce(row: dict, line: int) -> dict | None:
    name = (row.get("name") or "").strip()
    if not name:
        print(f"  line {line}: missing name — skipped", file=sys.stderr)
        return None
    out: dict = {"name": name, "domain": (row.get("domain") or "").strip() or None}
    for col in _INT_COLS:
        val = (row.get(col) or "").strip()
        try:
            out[col] = int(val) if val else None
        except ValueError:
            print(f"  line {line}: {col}={val!r} not an int — skipped", file=sys.stderr)
            return None
    for col in _FLOAT_COLS:
        val = (row.get(col) or "").strip()
        try:
            out[col] = float(val) if val else None
        except ValueError:
            print(f"  line {line}: {col}={val!r} not a float — skipped", file=sys.stderr)
            return None
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--replace", action="store_true", help="truncate historical_projects before import")
    args = ap.parse_args()

    try:
        f = open(args.csv_path, newline="", encoding="utf-8")
    except OSError as e:
        print(f"cannot open {args.csv_path}: {e}", file=sys.stderr)
        return 2

    db = SessionLocal()
    inserted = updated = skipped = 0
    try:
        if args.replace:
            n = db.query(HistoricalProject).delete()
            print(f"--replace: cleared {n} existing rows")

        with f:
            reader = csv.DictReader(f)
            missing = set(("name",)) - set(reader.fieldnames or [])
            if missing:
                print(f"CSV missing required column(s): {missing}", file=sys.stderr)
                return 2
            for i, row in enumerate(reader, start=2):  # line 1 = header
                data = _coerce(row, i)
                if data is None:
                    skipped += 1
                    continue
                existing = (
                    db.query(HistoricalProject)
                    .filter(HistoricalProject.name == data["name"])
                    .first()
                )
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    updated += 1
                else:
                    db.add(HistoricalProject(**data))
                    inserted += 1
        db.commit()
        print(f"done: {inserted} inserted, {updated} updated, {skipped} skipped")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
