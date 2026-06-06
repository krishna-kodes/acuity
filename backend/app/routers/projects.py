from fastapi import APIRouter, File, UploadFile

from app.schemas.project import ProjectCreate
from app.schemas.clarification import ClarificationCreate

router = APIRouter(tags=["projects"])


@router.post("/projects")
def create_project(body: ProjectCreate):
    pass


@router.post("/projects/{project_id}/documents")
def upload_document(project_id: str, file: UploadFile = File(...)):
    pass


@router.get("/projects/{project_id}/tbds")
def get_tbds(project_id: str):
    pass


@router.post("/projects/{project_id}/clarifications")
def create_clarification(project_id: str, body: ClarificationCreate):
    pass


@router.post("/projects/{project_id}/proposal")
def generate_proposal(project_id: str):
    pass


@router.get("/projects/{project_id}/proposal")
def get_proposal(project_id: str):
    pass


@router.post("/projects/{project_id}/stack")
def suggest_stack(project_id: str):
    pass


@router.post("/projects/{project_id}/estimate")
def estimate_effort(project_id: str):
    pass


@router.post("/projects/{project_id}/sync")
def sync_to_github(project_id: str):
    pass


@router.get("/projects/{project_id}/metrics")
def get_metrics(project_id: str):
    pass
