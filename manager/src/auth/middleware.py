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
from ..core.security import CertificateManager

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Единый middleware для гибридной аутентификации.

    - Публичные и machine-эндпоинты (агенты/сканер) пропускаются без JWT.
    - Для остальных /api/* проверяется JWT (cookie или Bearer),
      затем SPNEGO (hybrid/windows_integrated), затем Basic (local/hybrid).
    - Для machine-эндпоинтов опционально проверяется mTLS (клиентский сертификат).
    """

    def __init__(
        self,
        app,
        auth_manager: AuthManager,
        db_session_factory=None,
        cert_manager: CertificateManager = None,
    ):
        super().__init__(app)
        self.auth_manager = auth_manager
        self.db_session_factory = db_session_factory
        self.cert_manager = cert_manager

        # Публичные эндпоинты (не требуют аутентификации)
        self.public_paths = [
            "/api/auth/login",
            "/api/auth/mode",
            "/api/auth/refresh",
            "/api/health",
            "/api/root",
            "/api/folders/pick",
            "/metrics",       # публичные Manager-метрики Prometheus (docs/monitoring.md:104-105)
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
            "/api/audit/permissions",
            "/api/findings/check-fingerprints",
        ]

    def _is_public(self, path: str) -> bool:
        if any(path.startswith(p) for p in self.public_paths):
            return True
        # /api/scanner/* НЕ публичный здесь: он попадает в _is_machine_endpoint,
        # где JWT извлекается и request.state.user устанавливается (BUG-048b),
        # чтобы RBAC-dependency (require_admin и т.п.) получала корректного user.
        if any(path.startswith(p) for p in self.machine_prefixes):
            return True
        return False

    def _is_machine_endpoint(self, path: str) -> bool:
        if any(path.startswith(p) for p in self.machine_prefixes):
            return True
        if path == "/api/scanner" or path.startswith("/api/scanner/"):
            return True
        return False

    def _check_mtls(self, request: Request) -> Optional[JSONResponse]:
        """Проверка клиентского сертификата (mTLS) для machine-эндпоинтов.

        Если mTLS недоступен (relaxed, нет сертификатов) — пропускаем (None).
        Если сертификат есть — проверяем через CertificateManager.
        Возвращает None при успехе или error-ответ.
        """
        if not self.cert_manager or not self.cert_manager.is_available:
            return None

        transport = request.scope.get("transport")
        ssl_object = getattr(transport, "get_extra_info", lambda _: None)("ssl_object") \
            if transport else None

        if ssl_object is None:
            # mTLS strict: без сертификата — отклонить
            if self.cert_manager.strict:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Client certificate required (mTLS)"},
                )
            return None

        peer_cert = ssl_object.getpeercert()
        if not peer_cert:
            if self.cert_manager.strict:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Client certificate required (mTLS)"},
                )
            return None

        # Извлекаем CN и сохраняем в состояние
        try:
            cn = None
            for subj in peer_cert.get("subject", ()):
                for oid, val in subj:
                    if oid == "commonName":
                        cn = val
            if cn:
                request.state.client_cert_cn = cn
            else:
                request.state.client_cert_cn = None
        except Exception:
            request.state.client_cert_cn = None

        return None

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

        # Сохраняем возможность доступа к mTLS-сертификату агента для всех запросов
        try:
            transport = request.scope.get("transport")
            ssl_object = (
                transport.get_extra_info("ssl_object") if transport else None
            )
            if ssl_object is not None:
                peer = ssl_object.getpeercert()
                if peer:
                    for subj in peer.get("subject", ()):
                        for oid, val in subj:
                            if oid == "commonName":
                                request.state.client_cert_cn = val
        except Exception:
            pass

        if self._is_public(path):
            return await call_next(request)

        # mTLS-проверка для machine-эндпоинтов (агенты/сканер)
        if self._is_machine_endpoint(path):
            mtls_error = self._check_mtls(request)
            if mtls_error is not None:
                return mtls_error
            # TASK-004/TASK-005 (BUG-048): если передан валидный JWT —
            # устанавливаем пользователя (для RBAC-дефолтов require_admin и т.п.).
            # Без токена — machine-доступ (публичный, by design).
            token = self._extract_token(request)
            if token:
                payload = self.auth_manager.jwt.verify_token(token, "access")
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
                                    # BUG-048b: call_next ВНУТРИ try — сессия держится
                                    # открытой, пока хендлер читает roles (Detached).
                                    return await call_next(request)
                            finally:
                                db.close()
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
                    decoded = base64.b64decode(auth_header.replace("Basic ", "")).decode("utf-8")
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
