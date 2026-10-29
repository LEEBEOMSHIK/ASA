import hashlib
import hmac
import secrets
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, SecretStr

from asa.config import Settings

COOKIE = "asa_session"


@dataclass(frozen=True)
class Principal:
    user_id: str
    workspace_id: UUID
    roles: tuple[str, ...] = ("owner",)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_key: SecretStr


class OwnerSessions:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.failed_attempts: list[float] = []
        self.lock = threading.Lock()

    def test_login_available(self, request: Request) -> bool:
        loopback = {"127.0.0.1", "::1", "localhost"}
        return bool(
            self.settings.environment == "development"
            and self.settings.dev_login_enabled
            and request.client
            and request.client.host in loopback
            and request.url.hostname in loopback
        )

    def require_origin(self, request: Request) -> None:
        if request.headers.get("origin") not in self.settings.allowed_origins:
            raise HTTPException(403, "origin_not_allowed")

    def csrf(self, token: str) -> str:
        return hmac.new(
            self.settings.owner_access_key.get_secret_value().encode(),
            ("csrf:" + token).encode(),
            hashlib.sha256,
        ).hexdigest()

    def principal(self, request: Request) -> Principal:
        token = request.cookies.get(COOKIE, "")
        if not token or not self.settings.owner_access_key.get_secret_value():
            raise HTTPException(401, "login_required")
        if not self.settings.database_url:
            raise HTTPException(503, "registry_unconfigured")
        with psycopg.connect(self.settings.database_url, connect_timeout=3) as conn:
            row = conn.execute(
                "SELECT workspace_id FROM registry_sessions "
                "WHERE token_hash=%s AND expires_at>now()",
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
        if row is None or row[0] != self.settings.workspace_id:
            raise HTTPException(401, "login_required")
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            self.require_origin(request)
            if not hmac.compare_digest(request.headers.get("x-csrf-token", ""), self.csrf(token)):
                raise HTTPException(403, "csrf_invalid")
        return Principal(user_id="local-owner", workspace_id=row[0])

    def router(self) -> APIRouter:
        router = APIRouter(prefix="/api/v1")

        @router.get("/session/options")
        def options(request: Request) -> dict[str, bool]:
            return {"test_login_available": self.test_login_available(request)}

        @router.post("/session/test")
        def test_login(request: Request, response: Response) -> dict[str, str]:
            if not self.test_login_available(request):
                raise HTTPException(404, "not_found")
            self.require_origin(request)
            if urlsplit(request.headers.get("origin", "")).hostname not in {
                "127.0.0.1",
                "::1",
                "localhost",
            }:
                raise HTTPException(403, "origin_not_allowed")
            return issue_session(request, response)

        def issue_session(request: Request, response: Response) -> dict[str, str]:
            if (
                len(self.settings.owner_access_key.get_secret_value()) < 32
                or not self.settings.database_url
            ):
                raise HTTPException(503, "owner_login_unconfigured")
            token = secrets.token_urlsafe(32)
            with psycopg.connect(self.settings.database_url, connect_timeout=3) as conn:
                conn.execute("DELETE FROM registry_sessions WHERE expires_at<=now()")
                old = request.cookies.get(COOKIE)
                if old:
                    conn.execute(
                        "DELETE FROM registry_sessions WHERE token_hash=%s",
                        (hashlib.sha256(old.encode()).hexdigest(),),
                    )
                conn.execute(
                    "INSERT INTO registry_sessions VALUES (%s,%s,now()+interval '8 hours')",
                    (hashlib.sha256(token.encode()).hexdigest(), self.settings.workspace_id),
                )
            response.set_cookie(
                COOKIE,
                token,
                httponly=True,
                samesite="strict",
                secure=self.settings.secure_cookie,
                max_age=28800,
                path="/api/v1",
            )
            return {"csrf_token": self.csrf(token), "workspace_id": str(self.settings.workspace_id)}

        @router.post("/session")
        def login(body: Login, request: Request, response: Response) -> dict[str, str]:
            self.require_origin(request)
            expected = self.settings.owner_access_key.get_secret_value()
            if len(expected) < 32 or not self.settings.database_url:
                raise HTTPException(503, "owner_login_unconfigured")
            with self.lock:
                now = time.monotonic()
                self.failed_attempts = [t for t in self.failed_attempts if now - t < 60]
                if len(self.failed_attempts) >= 5:
                    raise HTTPException(429, "login_rate_limited")
                if not hmac.compare_digest(body.access_key.get_secret_value(), expected):
                    self.failed_attempts.append(now)
                    raise HTTPException(401, "invalid_access_key")
            return issue_session(request, response)

        @router.get("/session")
        def current(
            request: Request, principal: Principal = Depends(self.principal)
        ) -> dict[str, str]:
            return {
                "csrf_token": self.csrf(request.cookies[COOKIE]),
                "workspace_id": str(principal.workspace_id),
            }

        @router.delete("/session", status_code=204)
        def logout(
            request: Request, response: Response, principal: Principal = Depends(self.principal)
        ) -> None:
            with psycopg.connect(self.settings.database_url, connect_timeout=3) as conn:
                conn.execute(
                    "DELETE FROM registry_sessions WHERE token_hash=%s AND workspace_id=%s",
                    (
                        hashlib.sha256(request.cookies[COOKIE].encode()).hexdigest(),
                        principal.workspace_id,
                    ),
                )
            response.delete_cookie(
                COOKIE,
                path="/api/v1",
                httponly=True,
                secure=self.settings.secure_cookie,
                samesite="strict",
            )

        return router
