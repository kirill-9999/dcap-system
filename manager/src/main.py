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

app = FastAPI(
    title="DCAP System Manager",
    description="Data-Centric Audit and Protection System",
    version="2.0.0-alpha"
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


# ============================================================
# API ЭНДПОИНТЫ
# ============================================================

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "2.0.0-alpha"}


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

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "manager.src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )