📋 ТЗ — ДЕНЬ 29.5: УНИФИКАЦИЯ MANAGER И WEBUI (ВАРИАНТ А)
Файл: prompts/tz/day_29.5_manager_webui_unification.md
Дата: 29.08.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Реализовать Вариант А (компромиссный) — устранить дублирование БД и API между Manager и WebUI, сохранив раздельные процессы.

Основные задачи
WebUI переходит на SQLAlchemy — единый доступ к БД через manager/src/db/session.py

WebUI проксирует API-запросы в Manager — устранение дублирования эндпоинтов

Порты настраиваются через конфиги — manager/config/config.json и webui/config/config.json

Единый скрипт запуска — run_all.py для одновременного старта обоих процессов

Обновление Docker Compose — единый стек с зависимостями

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ / СОЗДАНИЯ
ИЗМЕНИТЬ
Файл	Изменение
webui/api/routes.py	Переход с raw sqlite на SQLAlchemy get_db(). Удаление дублирующих API-эндпоинтов (прокси в Manager).
webui/config.py	Добавление MANAGER_URL, DATABASE_URL, PORT
webui/main.py	Использование config.py для порта и настроек
manager/config/config.json	Добавление секции webui с port и enabled
webui/config/config.json	Добавление секции manager с url
manager/src/main.py	Добавление CORS для WebUI (если отсутствует)
docker-compose.yml	Обновление с учетом новой архитектуры
AGENTS.md	Обновление документации по запуску
README.md	Обновление документации
СОЗДАТЬ
Файл	Назначение
run_all.py	Единый скрипт запуска Manager + WebUI
shared/db.py	Общие SQLAlchemy утилиты (если нужны)
scripts/run_all.sh	Shell-версия единого запуска
УДАЛИТЬ / ДЕПРЕКИРОВАТЬ
Файл	Причина
webui/api/routes.py — дублирующие эндпоинты	Заменены на прокси в Manager
webui/config.py — дублирующие настройки БД	Перенесены в shared/config_loader.py
📋 ДЕТАЛЬНОЕ ТЗ
1. Обновить manager/config/config.json
json
{
    "server": {
        "host": "0.0.0.0",
        "port": 8000
    },
    "database": {
        "url": "sqlite:///./dcap.db"
    },
    "webui": {
        "enabled": true,
        "port": 8001,
        "host": "0.0.0.0"
    },
    "logging": {
        "level": "INFO"
    }
}
2. Создать/обновить webui/config/config.json
json
{
    "server": {
        "host": "0.0.0.0",
        "port": 8001
    },
    "manager": {
        "url": "http://localhost:8000"
    },
    "database": {
        "url": "sqlite:///../manager/dcap.db"
    },
    "logging": {
        "level": "INFO"
    }
}
3. Обновить webui/config.py
python
# webui/config.py
import os
import json
from pathlib import Path

CONFIG_PATH = os.environ.get("WEBUI_CONFIG", "config/config.json")

def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)

config = load_config()

# Server settings
WEBUI_HOST = config.get("server", {}).get("host", "0.0.0.0")
WEBUI_PORT = config.get("server", {}).get("port", 8001)

# Manager URL
MANAGER_URL = config.get("manager", {}).get("url", "http://localhost:8000")

# Database (SQLAlchemy URL)
DATABASE_URL = config.get("database", {}).get("url", "sqlite:///../manager/dcap.db")

# Logging
LOG_LEVEL = config.get("logging", {}).get("level", "INFO")
4. Переписать webui/api/routes.py
Ключевые изменения:

Удалить все дублирующие API-эндпоинты (/api/audit, /api/audit/stats, /api/findings, /api/catalog, /api/resources, /api/scanners)

Оставить только прокси-эндпоинты — все запросы к Manager

Использовать SQLAlchemy для чтения данных, если нужно — но основная логика через прокси

python
# webui/api/routes.py (ОБНОВЛЕННЫЙ)
import httpx
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
import logging

from ..config import MANAGER_URL

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================
#  ПРОКСИ-ЭНДПОИНТЫ (все API запросы → Manager)
# ============================================================

@router.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_to_manager(request: Request, path: str):
    """Прокси всех API-запросов в Manager"""
    
    # Исключаем статику и HTML-страницы
    if path.startswith("static/") or path.startswith("vendor/"):
        return None  # пропускаем статику
    
    # Формируем URL для Manager
    url = f"{MANAGER_URL}/{path}"
    
    # Получаем тело запроса (для POST/PUT)
    body = None
    if request.method in ["POST", "PUT"]:
        try:
            body = await request.json()
        except:
            body = None
    
    # Получаем параметры запроса
    params = dict(request.query_params)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=request.method,
                url=url,
                params=params,
                json=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                }
            )
            
            return {
                "status_code": response.status_code,
                "content": response.json() if response.headers.get("content-type") == "application/json" else response.text
            }
    except httpx.ConnectError:
        logger.error(f"Cannot connect to Manager: {MANAGER_URL}")
        raise HTTPException(
            status_code=503,
            detail=f"Manager service unavailable at {MANAGER_URL}"
        )
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
#  СТРАНИЦЫ (HTML)
# ============================================================

# ... (страницы остаются без изменений, т.к. они используют прокси для API)

# ============================================================
#  СТАТИКА (локально)
# ============================================================

# Статика отдается напрямую из webui/static/
5. Обновить webui/main.py
python
# webui/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from .config import WEBUI_HOST, WEBUI_PORT, LOG_LEVEL
from .api.routes import router as api_router

import logging
logging.basicConfig(level=LOG_LEVEL)

app = FastAPI(
    title="DCAP WebUI",
    version="3.0.0",
    description="Enterprise UI для DCAP System (прокси к Manager API)"
)

# Пути
BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Статика
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Шаблоны
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# API роутер (прокси)
app.include_router(api_router)

# ============================================================
#  СТРАНИЦЫ (HTML)
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "page": "dashboard"}
    )

@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(request: Request):
    return templates.TemplateResponse(
        "catalog.html",
        {"request": request, "page": "catalog"}
    )

@app.get("/findings", response_class=HTMLResponse)
async def findings_page(request: Request):
    return templates.TemplateResponse(
        "findings.html",
        {"request": request, "page": "findings"}
    )

@app.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request):
    return templates.TemplateResponse(
        "resources.html",
        {"request": request, "page": "resources"}
    )

@app.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request):
    return templates.TemplateResponse(
        "audit.html",
        {"request": request, "page": "audit"}
    )

@app.get("/access", response_class=HTMLResponse)
async def access_page(request: Request):
    return templates.TemplateResponse(
        "access.html",
        {"request": request, "page": "access"}
    )

@app.get("/scanners", response_class=HTMLResponse)
async def scanners_page(request: Request):
    return templates.TemplateResponse(
        "scanners.html",
        {"request": request, "page": "scanners"}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return templates.TemplateResponse(
        "settings.html",
        {"request": request, "page": "settings"}
    )

# ============================================================
#  HEALTHCHECK (для WebUI)
# ============================================================

@app.get("/health")
async def health():
    """Healthcheck для WebUI"""
    return {"status": "ok", "component": "webui", "version": "3.0.0"}

# ============================================================
#  ЗАПУСК
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=WEBUI_HOST, port=WEBUI_PORT)
6. Создать run_all.py
python
#!/usr/bin/env python3
# run_all.py — Единый запуск Manager + WebUI

import subprocess
import sys
import time
import signal
import os
from pathlib import Path

def load_manager_config():
    """Загрузка порта Manager из конфига"""
    import json
    config_path = Path("manager/config/config.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            return config.get("server", {}).get("port", 8000)
    return 8000

def load_webui_config():
    """Загрузка порта WebUI из конфига"""
    import json
    config_path = Path("webui/config/config.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
            return config.get("server", {}).get("port", 8001)
    return 8001

def main():
    print("=" * 60)
    print("🚀 DCAP System — запуск Manager + WebUI")
    print("=" * 60)
    
    # Загрузка портов из конфигов
    manager_port = load_manager_config()
    webui_port = load_webui_config()
    
    print(f"📡 Manager: http://localhost:{manager_port}")
    print(f"🌐 WebUI:   http://localhost:{webui_port}")
    print("=" * 60)
    
    # Запуск Manager
    print("▶️  Starting Manager...")
    manager_process = subprocess.Popen(
        [sys.executable, "run_manager.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    # Ждем, пока Manager поднимется
    time.sleep(2)
    
    # Запуск WebUI
    print("▶️  Starting WebUI...")
    webui_process = subprocess.Popen(
        [sys.executable, "run_webui.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )
    
    print("=" * 60)
    print("✅ DCAP System запущена!")
    print(f"📡 Manager API: http://localhost:{manager_port}")
    print(f"🌐 WebUI:       http://localhost:{webui_port}")
    print("=" * 60)
    print("🛑 Нажмите Ctrl+C для остановки")
    print("=" * 60)
    
    # Обработка сигналов для graceful shutdown
    def signal_handler(sig, frame):
        print("\n🛑 Остановка...")
        manager_process.terminate()
        webui_process.terminate()
        
        # Ждем завершения
        manager_process.wait()
        webui_process.wait()
        
        print("✅ Все процессы остановлены")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Мониторинг процессов (если один упал — останавливаем все)
    try:
        while True:
            time.sleep(1)
            
            # Проверка Manager
            if manager_process.poll() is not None:
                print(f"❌ Manager завершился с кодом {manager_process.returncode}")
                print("🛑 Остановка WebUI...")
                webui_process.terminate()
                webui_process.wait()
                sys.exit(1)
            
            # Проверка WebUI
            if webui_process.poll() is not None:
                print(f"❌ WebUI завершился с кодом {webui_process.returncode}")
                print("🛑 Остановка Manager...")
                manager_process.terminate()
                manager_process.wait()
                sys.exit(1)
                
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
7. Обновить run_manager.py
python
# run_manager.py (ОБНОВЛЕННЫЙ)
#!/usr/bin/env python3

import sys
import os
import json
from pathlib import Path

# Добавляем manager/src в путь
sys.path.insert(0, str(Path(__file__).parent / "manager" / "src"))

def load_config():
    config_path = Path("manager/config/config.json")
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"server": {"host": "0.0.0.0", "port": 8000}}

def main():
    config = load_config()
    host = config.get("server", {}).get("host", "0.0.0.0")
    port = config.get("server", {}).get("port", 8000)
    
    import uvicorn
    from manager.src.main import app
    
    print(f"🚀 Starting Manager on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
8. Обновить run_webui.py
python
# run_webui.py (ОБНОВЛЕННЫЙ)
#!/usr/bin/env python3

import sys
import os
import json
from pathlib import Path

# Добавляем webui в путь
sys.path.insert(0, str(Path(__file__).parent / "webui"))

def load_config():
    config_path = Path("webui/config/config.json")
    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)
    return {"server": {"host": "0.0.0.0", "port": 8001}}

def main():
    config = load_config()
    host = config.get("server", {}).get("host", "0.0.0.0")
    port = config.get("server", {}).get("port", 8001)
    
    import uvicorn
    from webui.main import app
    
    print(f"🚀 Starting WebUI on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    main()
9. Обновить docker-compose.yml
yaml
# docker-compose.yml (ОБНОВЛЕННЫЙ)
version: '3.8'

services:
  manager:
    build:
      context: ./manager
      dockerfile: Dockerfile
    container_name: dcap-manager
    ports:
      - "${MANAGER_PORT:-8000}:8000"
    volumes:
      - ./manager/config:/app/config
      - ./manager/data:/app/data
      - ./manager/logs:/app/logs
    environment:
      - MANAGER_CONFIG=/app/config/config.json
    networks:
      - dcap-network
    restart: unless-stopped

  webui:
    build:
      context: ./webui
      dockerfile: Dockerfile
    container_name: dcap-webui
    ports:
      - "${WEBUI_PORT:-8001}:8001"
    volumes:
      - ./webui/config:/app/config
      - ./webui/logs:/app/logs
      - ./manager/data:/app/manager-data:ro  # Read-only доступ к БД
    environment:
      - WEBUI_CONFIG=/app/config/config.json
      - MANAGER_URL=http://manager:8000
    depends_on:
      - manager
    networks:
      - dcap-network
    restart: unless-stopped

networks:
  dcap-network:
    driver: bridge
10. Обновить AGENTS.md
markdown
# AGENTS.md (обновленная секция запуска)

## Запуск

### Вариант 1: Единый запуск (рекомендуемый)

```bash
python run_all.py
Вариант 2: Раздельный запуск
bash
# Терминал 1: Manager (порт из manager/config/config.json)
python run_manager.py

# Терминал 2: WebUI (порт из webui/config/config.json)
python run_webui.py
Вариант 3: Docker Compose
bash
docker-compose up -d
Настройка портов
Manager: manager/config/config.json → server.port

WebUI: webui/config/config.json → server.port

Архитектура
Manager (API): :8000 (по умолчанию) — control-plane

WebUI (UI): :8001 (по умолчанию) — дашборд, проксирует API в Manager

text

---

## ✅ КРИТЕРИИ ПРИЕМКИ

### БД и API

- [ ] WebUI использует SQLAlchemy `get_db()` из Manager (или прокси)
- [ ] Все дублирующие API-эндпоинты удалены из WebUI
- [ ] WebUI проксирует API-запросы в Manager
- [ ] Форматы ответов унифицированы

### Конфигурация

- [ ] Порт Manager настраивается через `manager/config/config.json`
- [ ] Порт WebUI настраивается через `webui/config/config.json`
- [ ] `MANAGER_URL` настраивается через `webui/config/config.json`
- [ ] Переменные окружения имеют приоритет над конфигами

### Запуск

- [ ] `run_all.py` запускает оба процесса
- [ ] При падении одного процесса — останавливается второй
- [ ] `Ctrl+C` корректно останавливает оба процесса
- [ ] `docker-compose up -d` запускает оба контейнера

### Документация

- [ ] `AGENTS.md` обновлена
- [ ] `README.md` обновлена
- [ ] `project_plan.md` обновлен

### Тестирование

- [ ] Manager запускается отдельно и работает
- [ ] WebUI запускается отдельно и работает
- [ ] `run_all.py` запускает оба процесса
- [ ] WebUI корректно проксирует API в Manager
- [ ] Все страницы WebUI работают

---

## 🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

```bash
# 1. Проверка конфигов
cat manager/config/config.json | grep port
cat webui/config/config.json | grep port

# 2. Запуск через run_all.py
python run_all.py
# Должны запуститься оба процесса

# 3. Проверка Manager
curl http://localhost:8000/health

# 4. Проверка WebUI (прокси)
curl http://localhost:8001/api/audit/stats
# Должен вернуть данные от Manager

# 5. Проверка страниц
open http://localhost:8001
open http://localhost:8001/catalog
open http://localhost:8001/audit

# 6. Проверка Docker Compose
docker-compose up -d
docker-compose ps
docker-compose logs webui | grep "Manager"
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_29.5_manager_webui_unification
git add .
git commit -m "feat: День 29.5 — Унификация Manager и WebUI (Вариант А)

- WebUI переведен на SQLAlchemy (единая БД-логика)
- Удалены дублирующие API-эндпоинты из WebUI
- WebUI проксирует API-запросы в Manager
- Порты настраиваются через конфиги (manager/config/config.json, webui/config/config.json)
- Создан run_all.py для единого запуска
- Обновлен docker-compose.yml
- Обновлена документация (AGENTS.md, README.md)"