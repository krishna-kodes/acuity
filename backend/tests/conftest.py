import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app import models as _all_models  # noqa: F401 — registers all ORM models with Base.metadata
from app.models.base import Base
from app.models.enums import ProjectPhase, ProjectStatus
from app.models.project import Project, Proposal


@pytest.fixture(scope="function")
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()

    # Project at phase=estimation so /stack and /estimate phase guards pass
    project = Project(name="Test Project", phase=ProjectPhase.estimation, status=ProjectStatus.active)
    session.add(project)
    session.flush()

    # Pre-create a proposal so GET /proposal returns 200
    proposal = Proposal(project_id=project.id, document_id=0, content_path="documents/stub.docx")
    session.add(proposal)
    session.commit()

    yield session
    session.close()


@pytest.fixture
def client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def project_id(db_session) -> str:
    """Return the integer ID of the pre-seeded test project as a string."""
    project = db_session.query(Project).first()
    return str(project.id)
