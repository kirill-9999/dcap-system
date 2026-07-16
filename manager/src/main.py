from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

from .db import init_db
from .api import (
    resources_router,
    scanner_router,
    tasks_router,
    findings_router,
    catalog_router
)

# Инициализация FastAPI
app = FastAPI(
    title="DCAP Manager API",
    description="Data Classification and Protection System - Manager",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(resources_router)
app.include_router(scanner_router)
app.include_router(tasks_router)
app.include_router(findings_router)
app.include_router(catalog_router)

# Статические файлы WebUI
webui_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "webui", "static")
if os.path.exists(webui_path):
    app.mount("/static", StaticFiles(directory=webui_path), name="static")
    
    @app.get("/")
    async def root():
        from fastapi.responses import FileResponse
        index_path = os.path.join(webui_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "DCAP Manager API", "docs": "/docs"}

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске"""
    print("🚀 DCAP Manager starting...")
    init_db()
    print("✅ Database initialized")

@app.get("/health")
async def health_check():
    """Проверка здоровья"""
    return {"status": "healthy", "version": "1.0.0"}

if __name__ == "__main__":
    uvicorn.run(
        "manager.src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )