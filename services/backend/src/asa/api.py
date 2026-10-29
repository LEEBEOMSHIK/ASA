from collections.abc import Awaitable, Callable

import psycopg
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from asa.auth.session import OwnerSessions
from asa.config import Settings
from asa.registry.automations import automation_router
from asa.registry.history import history_router
from asa.registry.routes import registry_router
from asa.registry.runtime import runtime_router
from asa.registry.schemas import RegistryError
from asa.registry.script_routes import script_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="AI Shorts Studio", version="0.1.0")
    sessions = OwnerSessions(settings)
    app.include_router(sessions.router())
    app.include_router(registry_router(settings, sessions))
    app.include_router(history_router(settings, sessions))
    app.include_router(script_router(settings, sessions))
    app.include_router(automation_router(settings, sessions))
    app.include_router(runtime_router(settings, sessions))

    @app.middleware("http")
    async def request_limits(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in ("POST", "PATCH", "PUT"):
            length = request.headers.get("content-length", "")
            if not length.isdigit():
                return JSONResponse({"detail": "content_length_required"}, status_code=411)
            if int(length) > 65536:
                return JSONResponse({"detail": "payload_too_large"}, status_code=413)
            if len(await request.body()) > 65536:
                return JSONResponse({"detail": "payload_too_large"}, status_code=413)
        response = await call_next(request)
        if request.url.path.startswith("/api/v1"):
            response.headers["Cache-Control"] = "no-store"
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
            with psycopg.connect(settings.database_url, connect_timeout=3) as connection:
                connection.execute("SELECT 1")
        except psycopg.Error:
            return JSONResponse({"status": "not_ready", "database": "unavailable"}, status_code=503)
        return JSONResponse({"status": "ready", "database": "connected"})

    return app


app = create_app()
