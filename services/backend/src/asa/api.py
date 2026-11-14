from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from asa.auth.session import OwnerSessions
from asa.config import Settings
from asa.database import close_database, connection
from asa.registry.art_style_catalog import catalog_router
from asa.registry.audio_routes import audio_router
from asa.registry.automation_categories import automation_category_router
from asa.registry.automations import automation_router
from asa.registry.branding import branding_router
from asa.registry.categories import category_router
from asa.registry.characters import character_router
from asa.registry.history import history_router
from asa.registry.library_routes import library_router
from asa.registry.model_catalog import model_catalog_router
from asa.registry.monitoring import monitoring_router
from asa.registry.navigation_colors import navigation_colors_router
from asa.registry.profile import profile_router
from asa.registry.routes import registry_router
from asa.registry.runtime import runtime_router
from asa.registry.schemas import RegistryError
from asa.registry.script_routes import script_router
from asa.registry.video_jobs import video_job_router
from asa.registry.video_planning import video_planning_router
from asa.registry.work_management import management_router
from asa.registry.worker_routes import worker_router
from asa.video_management import video_management_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        close_database(settings.database_url)

    app = FastAPI(title="AI Shorts Studio", version="0.1.0", lifespan=lifespan)
    sessions = OwnerSessions(settings)
    app.include_router(worker_router(settings, sessions))

    app.include_router(sessions.router())
    app.include_router(profile_router(settings, sessions))
    app.include_router(navigation_colors_router(settings, sessions))
    app.include_router(registry_router(settings, sessions))
    app.include_router(management_router(settings, sessions))
    app.include_router(history_router(settings, sessions))
    app.include_router(script_router(settings, sessions))
    app.include_router(automation_router(settings, sessions))
    app.include_router(runtime_router(settings, sessions))
    app.include_router(monitoring_router(settings, sessions))
    app.include_router(model_catalog_router(settings, sessions))
    app.include_router(character_router(settings, sessions))
    app.include_router(category_router(settings, sessions))
    app.include_router(automation_category_router(settings, sessions))
    app.include_router(branding_router(settings, sessions))
    app.include_router(catalog_router(settings, sessions))
    app.include_router(video_planning_router(settings, sessions))
    app.include_router(video_job_router(settings, sessions))
    app.include_router(video_management_router(settings, sessions))
    app.include_router(audio_router(settings, sessions))
    app.include_router(library_router(settings, sessions))

    @app.middleware("http")
    async def request_limits(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in ("POST", "PATCH", "PUT"):
            length = request.headers.get("content-length", "")
            if not length.isdigit():
                return JSONResponse({"detail": "content_length_required"}, status_code=411)
            parts = request.url.path.strip('/').split('/')
            agent_definition = (parts == ['api', 'v1', 'agents']
                                or parts == ['api', 'v1', 'agents', 'save']
                                or (len(parts) == 5 and parts[:3] == ['api', 'v1', 'agents']
                                    and parts[4] in {'save', 'draft'}))
            # Five bounded instruction bodies, including JSON-escaped Unicode, plus settings.
            limit = (4 * 1024 * 1024 if agent_definition else
                     28001000 if request.url.path == '/api/v1/video-references' else
                     7100000 if request.url.path == '/api/v1/characters/library/uploads'
                     else 65536)
            if int(length) > limit:
                return JSONResponse({"detail": "payload_too_large"}, status_code=413)
            if len(await request.body()) > limit:
                return JSONResponse({"detail": "payload_too_large"}, status_code=413)
        response = await call_next(request)
        if request.url.path.startswith("/api/v1"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    @app.exception_handler(RegistryError)
    async def registry_error(request: Request, error: RegistryError) -> JSONResponse:
        return JSONResponse(
            {"detail": error.code, "issues": [i.model_dump() for i in error.issues]},
            status_code=error.status,
        )

    @app.exception_handler(psycopg.Error)
    async def database_error(request: Request, error: psycopg.Error) -> JSONResponse:
        return JSONResponse({"detail": "registry_database_unavailable"}, status_code=503)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            {
                "detail": "invalid_request",
                "issues": [
                    {
                        "field_path": ".".join(map(str, e["loc"])),
                        "message": e["msg"],
                        "code": e["type"],
                    }
                    for e in error.errors()
                ],
            },
            status_code=422,
        )

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/health/ready")
    def ready() -> JSONResponse:
        if not settings.database_url:
            return JSONResponse(
                {"status": "not_ready", "database": "unconfigured"}, status_code=503
            )
        try:
            with connection(settings.database_url) as conn:
                conn.execute("SELECT 1")
        except psycopg.Error:
            return JSONResponse({"status": "not_ready", "database": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready", "database": "connected"})

    return app


app = create_app()
