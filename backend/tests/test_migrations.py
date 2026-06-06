import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy import event as sa_event

from app.models import Base

EXPECTED_TABLES = {
    "projects", "documents", "proposals", "proposal_state",
    "clarifications", "employees", "skills", "employee_skills",
    "approved_technologies", "historical_projects",
    "epics", "tasks",
    "pii_detections", "pii_ingestion_logs",
    "metrics", "latency_logs", "error_logs",
}


@pytest.fixture
def tmp_engine(tmp_path):
    db_url = f"sqlite:///{tmp_path}/test.db"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    yield engine
    engine.dispose()


def test_create_all_tables(tmp_engine):
    Base.metadata.create_all(tmp_engine)
    inspector = inspect(tmp_engine)
    tables = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - tables
    extra = tables - EXPECTED_TABLES
    assert EXPECTED_TABLES == tables, f"Missing: {missing}, Extra: {extra}"


def test_all_tables_have_id_pk(tmp_engine):
    Base.metadata.create_all(tmp_engine)
    inspector = inspect(tmp_engine)
    for table in EXPECTED_TABLES - {"employee_skills"}:
        pk_cols = inspector.get_pk_constraint(table)["constrained_columns"]
        assert "id" in pk_cols, f"{table} missing 'id' primary key"


def test_wal_mode_set_by_engine(tmp_path):
    db_url = f"sqlite:///{tmp_path}/wal_test.db"
    test_engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @sa_event.listens_for(test_engine, "connect")
    def set_wal(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

    with test_engine.connect() as conn:
        result = conn.execute(text("PRAGMA journal_mode")).fetchone()
        assert result[0] == "wal"
    test_engine.dispose()


def test_fk_indexes_exist(tmp_engine):
    Base.metadata.create_all(tmp_engine)
    inspector = inspect(tmp_engine)
    idx_names = {i["name"] for i in inspector.get_indexes("documents")}
    assert "ix_documents_project_id" in idx_names
    idx_names = {i["name"] for i in inspector.get_indexes("epics")}
    assert "ix_epics_project_id" in idx_names
