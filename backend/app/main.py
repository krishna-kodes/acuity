import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.services.metrics_tracker import CostBudgetExceededError
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.config import settings
from app.routers.admin import router as admin_router
from app.routers.factory import router as factory_router
from app.routers.projects import router as projects_router

# Gate the docs behind HTTP Basic auth only when DOCS_PASSWORD is set; otherwise
# serve them openly (local dev). When gated, FastAPI's built-in docs are
# disabled and replaced with auth-protected routes below.
_docs_protected = bool(settings.docs_password)
_fastapi_kwargs: dict = {"title": "Acuity API", "version": "1.0.0"}
if _docs_protected:
    _fastapi_kwargs.update(docs_url=None, redoc_url=None, openapi_url=None)

app = FastAPI(**_fastapi_kwargs)

_basic = HTTPBasic()


def _require_docs_auth(credentials: HTTPBasicCredentials = Depends(_basic)) -> None:
    user_ok = secrets.compare_digest(credentials.username, settings.docs_username)
    pass_ok = secrets.compare_digest(credentials.password, settings.docs_password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid documentation credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )


if _docs_protected:
    @app.get("/openapi.json", include_in_schema=False)
    def _openapi(_: None = Depends(_require_docs_auth)) -> dict:
        return app.openapi()

    @app.get("/docs", include_in_schema=False)
    def _swagger(_: None = Depends(_require_docs_auth)):
        return get_swagger_ui_html(openapi_url="/openapi.json", title="Acuity API — Docs")

    @app.get("/redoc", include_in_schema=False)
    def _redoc(_: None = Depends(_require_docs_auth)):
        return get_redoc_html(openapi_url="/openapi.json", title="Acuity API — ReDoc")

cors_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects_router, prefix="/api/v1")
app.include_router(
    factory_router,
    prefix="/api/v1",
    include_in_schema=settings.expose_factory_in_docs,
)
app.include_router(admin_router, prefix="/api/v1")


@app.exception_handler(CostBudgetExceededError)
async def _cost_budget_handler(_request, exc: CostBudgetExceededError):
    # 402 Payment Required — workflow hit MAX_COST_PER_WORKFLOW_USD ceiling.
    return JSONResponse(status_code=402, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
