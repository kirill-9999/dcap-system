from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from webui.api.routes import router
from webui.config import WEBUI_HOST, WEBUI_PORT, DEBUG

app = FastAPI(title="DCAP WebUI", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(router)

HTML_PATH = Path(__file__).parent / "static" / "index_simple.html"

def get_html():
    if HTML_PATH.exists():
        with open(HTML_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>Error: index_simple.html not found</h1>"

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTMLResponse(content=get_html())

@app.get("/findings", response_class=HTMLResponse)
async def findings():
    return HTMLResponse(content=get_html())

@app.get("/tasks", response_class=HTMLResponse)
async def tasks():
    return HTMLResponse(content=get_html())

@app.get("/scanners", response_class=HTMLResponse)
async def scanners():
    return HTMLResponse(content=get_html())

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════╗
    ║   DCAP WebUI v3.0                          ║
    ║   http://localhost:8001                    ║
    ╚══════════════════════════════════════════════╝
    """)
    uvicorn.run(
        "webui.main_simple:app",
        host=WEBUI_HOST,
        port=WEBUI_PORT,
        reload=DEBUG,
        log_level="info"
    )