import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def ensure_sqlite_dir(db_url: str) -> None:
    """Create the parent directory for a file-based sqlite URL.

    Railway/containers point APP_DB_PATH at a volume (e.g. sqlite:////data/app.db);
    sqlite raises "unable to open database file" if that directory is absent.
    """
    url = make_url(db_url)
    if url.drivername.startswith("sqlite") and url.database and url.database != ":memory:":
        parent = os.path.dirname(os.path.abspath(url.database))
        if parent:
            os.makedirs(parent, exist_ok=True)


ensure_sqlite_dir(settings.app_db_path)

engine = create_engine(
    settings.app_db_path,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, _record):
    dbapi_conn.execute("PRAGMA journal_mode=WAL")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
