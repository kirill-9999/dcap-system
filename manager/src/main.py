# manager/src/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi import HTTPException

from manager.src.api.resources import router as resources_router
from manager.src.api.tasks import router as tasks_router
from manager.src.api.findings import router as findings_router
from manager.src.api.catalog import router as catalog_router
from manager.src.api.scanner import router as scanner_router
from manager.src.api.permissions import router as permissions_router
from manager.src.api.audit import router as audit_router
from manager.src.api.webui import router as webui_router
from manager.src.api.retention import router as retention_router

from manager.src.config import get_config
from manager.src.auth.manager import AuthManager
from manager.src.auth.middleware import AuthMiddleware
from manager.src.auth.router import router as auth_router, set_auth_manager
from manager.src.core.security import CertificateManager
from manager.src.db import session

app = FastAPI(
    title="DCAP System Manager",
    description="Data-Centric Audit and Protection System",
    version="3.3.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# АУТЕНТИФИКАЦИЯ (День 30)
# ============================================================

_config = get_config()
_auth_manager = AuthManager(_config)
set_auth_manager(_auth_manager)

# ============================================================
# БЕЗОПАСНОСТЬ / mTLS (День 34)
# ============================================================

_security_config = {
    "mtls_enabled": _config.get("security", {}).get("mtls_enabled", False),
    "mtls_strict": _config.get("security", {}).get("mtls_strict", False),
    "certs_dir": _config.get("security", {}).get("certs_dir", "certs"),
}

_cert_manager = CertificateManager(_security_config)

if _cert_manager.is_available:
    import logging

    sec_logger = logging.getLogger("dcap.security")
    sec_logger.warning("mTLS is active for Manager")
else:
    if _security_config["mtls_enabled"]:
        import logging

        sec_logger = logging.getLogger("dcap.security")
        sec_logger.warning(
            "mTLS enabled but certificates missing — server runs on plain HTTP " "(relaxed mode)"
        )

app.add_middleware(
    AuthMiddleware,
    auth_manager=_auth_manager,
    db_session_factory=session.SessionLocal,
    cert_manager=_cert_manager,
)


# ============================================================
# UI
# Каноничный WebUI — webui/main.py на порту :8001 (python run_webui.py).
# Manager — чистое API: легаси-статика удалена, корень редиректит на UI.
# ============================================================


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse(url="http://localhost:8001")


# ============================================================
# ПОДКЛЮЧЕНИЕ РОУТЕРОВ
# ============================================================

app.include_router(resources_router)
app.include_router(tasks_router)
app.include_router(findings_router)
app.include_router(catalog_router)
app.include_router(scanner_router)
app.include_router(permissions_router)
app.include_router(audit_router)
app.include_router(webui_router)
app.include_router(retention_router)
app.include_router(auth_router)


# ============================================================
# API ЭНДПОИНТЫ
# ============================================================


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "3.3.0"}


@app.post("/api/folders/pick")
def pick_folder():
    """Открыть нативный диалог выбора папки (Windows)"""
    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Выбор папки для сканирования")
        root.destroy()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Невозможно открыть диалог выбора папки: {e}")
    if not path:
        return {"success": False, "path": None}
    return {"success": True, "path": path}


@app.get("/api/root")
async def api_root():
    return {"message": "DCAP System Manager API", "docs": "/docs"}


# ============================================================
# ЗАПУСК СЕРВЕРА
# ============================================================


@app.on_event("startup")
async def on_startup():
    """Создание таблиц и инициализация ролей/admin при старте."""
    try:
        session.init_db()
        from manager.src.db.init_roles import init_roles_and_admin

        db = session.SessionLocal()
        try:
            init_roles_and_admin(db)
        finally:
            db.close()
    except Exception as e:
        print(f"[auth] Ошибка инициализации ролей: {e}")

    # День 35: периодическая архивация данных (фоновый поток вместо Celery)
    try:
        from manager.src.retention.scheduler import start_scheduler

        start_scheduler()
    except Exception as e:
        print(f"[retention] Ошибка запуска планировщика: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("manager.src.main:app", host="0.0.0.0", port=8000, reload=True)
