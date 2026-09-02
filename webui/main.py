# webui/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys

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

BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)

app.include_router(router)


def render(request: Request, name: str, page: str):
    return templates.TemplateResponse(request, name, {"page": page})


@app.get("/", response_class=HTMLResponse)
async def page_dashboard(request: Request):
    return render(request, "dashboard.html", "Дашборд")


@app.get("/catalog", response_class=HTMLResponse)
async def page_catalog(request: Request):
    return render(request, "catalog.html", "Каталог")


@app.get("/findings", response_class=HTMLResponse)
async def page_findings(request: Request):
    return render(request, "findings.html", "Находки")


@app.get("/resources", response_class=HTMLResponse)
async def page_resources(request: Request):
    return render(request, "resources.html", "Ресурсы")


@app.get("/audit", response_class=HTMLResponse)
async def page_audit(request: Request):
    return render(request, "audit.html", "Аудит")


@app.get("/access", response_class=HTMLResponse)
async def page_access(request: Request):
    return render(request, "access.html", "Доступ")


@app.get("/scanners", response_class=HTMLResponse)
async def page_scanners(request: Request):
    return render(request, "scanners.html", "Сканеры")


@app.get("/users", response_class=HTMLResponse)
async def page_users(request: Request):
    return render(request, "users.html", "Пользователи")


@app.get("/roles", response_class=HTMLResponse)
async def page_roles(request: Request):
    return render(request, "roles.html", "Роли")


@app.get("/settings", response_class=HTMLResponse)
async def page_settings(request: Request):
    return render(request, "settings.html", "Настройки")


@app.get("/login", response_class=HTMLResponse)
async def page_login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"page": "Вход"})


if __name__ == "__main__":
    uvicorn.run(app, host=WEBUI_HOST, port=WEBUI_PORT, reload=DEBUG)
