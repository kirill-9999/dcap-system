# manager/src/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException
import os

from manager.src.api.resources import router as resources_router
from manager.src.api.tasks import router as tasks_router
from manager.src.api.findings import router as findings_router
from manager.src.api.catalog import router as catalog_router
from manager.src.api.scanner import router as scanner_router
from manager.src.api.permissions import router as permissions_router
from manager.src.api.audit import router as audit_router

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
# ПОДКЛЮЧЕНИЕ WEBUI
# ============================================================

# Определяем путь к static
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
webui_static = os.path.join(base_dir, "webui", "static")
webui_static = os.path.normpath(webui_static)

print(f"📁 WebUI static: {webui_static}")
print(f"📁 Exists: {os.path.exists(webui_static)}")

# Проверяем наличие файлов
index_path = os.path.join(webui_static, "index.html")
css_path = os.path.join(webui_static, "css", "style.css")
js_path = os.path.join(webui_static, "js", "app.js")

print(f"📁 index.html: {index_path} ({'✅' if os.path.exists(index_path) else '❌'})")
print(f"📁 style.css: {css_path} ({'✅' if os.path.exists(css_path) else '❌'})")
print(f"📁 app.js: {js_path} ({'✅' if os.path.exists(js_path) else '❌'})")

if os.path.exists(webui_static):
    # ✅ 1. Монтируем ВСЮ папку static на /static
    app.mount("/static", StaticFiles(directory=webui_static), name="static")
    print("✅ Static files mounted on /static")
    
    # ✅ 2. Отдаем index.html на корневой путь
    @app.get("/")
    async def serve_index():
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "index.html not found", "path": index_path}
    
    # ✅ 3. Если нужен прямой доступ к index.html
    @app.get("/index.html")
    async def serve_index_html():
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "index.html not found"}
    
    print("✅ WebUI настроен")
else:
    print(f"❌ WebUI не найден по пути: {webui_static}")
    
    @app.get("/")
    async def root():
        return {
            "message": "DCAP System Manager API",
            "docs": "/docs",
            "error": "WebUI not found",
            "path": webui_static
        }

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