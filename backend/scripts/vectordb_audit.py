"""Vector DB integrity tool — detect and prune orphan ChromaDB collections.

An "orphan" is a `project_<id>` collection whose `<id>` has no row in
app.db `projects`. Orphans cause stale-document bugs: a reused project URL
retrieves a previously-ingested document's embeddings.

Usage (run from backend/):
    python scripts/vectordb_audit.py            # report only
    python scripts/vectordb_audit.py --prune    # delete orphan collections + their checkpointer threads

Run with the backend server stopped to avoid racing live requests.
"""
import argparse
import os
import sqlite3
import sys

import chromadb

APP_DB = os.environ.get("APP_DB_PATH", "./app.db")
STATE_DB = os.environ.get("CHECKPOINT_DB_PATH", "./project_state.db")
CHROMA_PATH = os.environ.get("CHROMA_PERSIST_PATH", "./chroma_db")


def _project_ids() -> set[str]:
    if not os.path.exists(APP_DB):
        print(f"!! {APP_DB} not found — cannot determine valid projects", file=sys.stderr)
        sys.exit(2)
    con = sqlite3.connect(APP_DB)
    try:
        return {str(r[0]) for r in con.execute("SELECT id FROM projects")}
    finally:
        con.close()


def _wipe_threads(thread_ids: set[str]) -> int:
    """Delete checkpointer rows for the given thread_ids. Returns rows deleted."""
    if not os.path.exists(STATE_DB) or not thread_ids:
        return 0
    con = sqlite3.connect(STATE_DB)
    deleted = 0
    try:
        qmarks = ",".join("?" * len(thread_ids))
        ids = tuple(thread_ids)
        for tbl in ("writes", "checkpoints"):
            try:
                cur = con.execute(f"DELETE FROM {tbl} WHERE thread_id IN ({qmarks})", ids)
                deleted += cur.rowcount or 0
            except sqlite3.OperationalError:
                pass
        con.commit()
    finally:
        con.close()
    return deleted


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prune", action="store_true", help="delete orphan collections + checkpointer threads")
    args = ap.parse_args()

    valid = _project_ids()
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collections = [c.name for c in client.list_collections()]

    orphans = []
    for name in collections:
        if not name.startswith("project_"):
            continue
        pid = name[len("project_"):]
        if pid not in valid:
            orphans.append((name, pid))

    print(f"valid projects (app.db): {len(valid)}")
    print(f"chroma collections:      {len(collections)}")
    print(f"orphan collections:      {len(orphans)}")
    for name, pid in orphans:
        print(f"  ORPHAN {name} (count={client.get_collection(name).count()})")

    if not orphans:
        print("clean — no orphans.")
        return 0

    if not args.prune:
        print("\nrun with --prune to delete them.")
        return 1

    orphan_ids = {pid for _, pid in orphans}
    for name, _ in orphans:
        client.delete_collection(name)
    rows = _wipe_threads(orphan_ids)
    print(f"\npruned {len(orphans)} collections + {rows} checkpointer rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
