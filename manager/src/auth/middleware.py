# manager/src/auth/middleware.py
import base64
import logging
from typing import Optional

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session

from .manager import AuthManager
from .modes import AuthMode
from .models import User

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Единый middleware для гибридной аутентификации.

    - Публичные и machine-эндпоинты (агенты/сканер) пропускаются без JWT.
    - Для остальных /api/* проверяется JWT (cookie или Bearer),
      затем SPNEGO (hybrid/windows_integrated), затем Basic (local/hybrid).
    """

    def __init__(self, app, auth_manager: AuthManager, db_session_factory=None):
        super().__init__(app)
        self.auth_manager = auth_manager
        self.db_session_factory = db_session_factory

        # Публичные эндпоинты (не требуют аутентификации)
        self.public_paths = [
            "/api/auth/login",
            "/api/auth/mode",
            "/api/auth/refresh",
            "/api/health",
            "/api/root",
            "/api/folders/pick",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/static",
            "/vendor",
        ]

        # Machine-эндпоинты (агенты/сканер) — API-ключи ожидаются в день 35-37,
        # поэтому сейчас они доступны без JWT.
        self.machine_prefixes = [
            "/api/scanner/register",
            "/api/scanner/heartbeat",
            "/api/scanner/tasks",
            "/api/audit/agents/register",
            "/api/audit/agents/heartbeat",
            "/api/audit/events",
        ]

    def _is_public(self, path: str) -> bool:
        if any(path.startswith(p) for p in self.public_paths):
            return True
        # Список сканеров (list) — machine-доступ для ManagedScanner, не блокируем
        if path == "/api/scanner" or path.startswith("/api/scanner/"):
            return True
        if any(path.startswith(p) for p in self.machine_prefixes):
            return True
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
        return token

    def _auth_required_headers(self) -> dict:
        if self.auth_manager.mode != AuthMode.LOCAL:
            return {"WWW-Authenticate": "Negotiate"}
        return {"WWW-Authenticate": "Bearer"}

    async def _get_db(self):
        if self.db_session_factory:
            return self.db_session_factory()
        return None

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if self._is_public(path):
            return await call_next(request)

        # 1. Проверка JWT (cookie или Bearer)
        token = self._extract_token(request)
        if token:
            payload = self.auth_manager.jwt.verify_token(token)
            if payload:
                user_id = payload.get("user_id")
                if user_id:
                    db = await self._get_db()
                    if db is not None:
                        try:
                            user = db.query(User).filter(User.id == user_id).first()
                            if user and user.is_active:
                                request.state.user = user
                                request.state.auth_method = "jwt"
                                return await call_next(request)
                        finally:
                            db.close()

        # 2. SPNEGO (Windows Integrated Auth)
        if self.auth_manager.mode != AuthMode.LOCAL:
            db = await self._get_db()
            if db is not None:
                try:
                    user = await self.auth_manager.authenticate_windows(request, db)
                    if user:
                        request.state.user = user
                        request.state.auth_method = "windows_integrated"
                        return await call_next(request)
                finally:
                    db.close()

        # 3. Basic Auth (local/hybrid)
        if self.auth_manager.mode in (AuthMode.LOCAL, AuthMode.HYBRID):
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Basic "):
                try:
                    decoded = base64.b64decode(
                        auth_header.replace("Basic ", "")
                    ).decode('utf-8')
                    username, password = decoded.split(":", 1)
                    db = await self._get_db()
                    if db is not None:
                        try:
                            user = await self.auth_manager.authenticate(
                                request, db, username, password
                            )
                            if user:
                                request.state.user = user
                                request.state.auth_method = "basic"
                                return await call_next(request)
                        finally:
                            db.close()
                except Exception:
                    pass

        # Не авторизован — 401
        return JSONResponse(
            status_code=401,
            headers=self._auth_required_headers(),
            content={"detail": "Authentication required"},
        )
