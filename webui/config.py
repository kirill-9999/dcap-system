import os

VERSION = "2.0.1"

# База данных
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///manager/dcap.db"
)

# WebUI настройки (127.0.0.1 — только локальный доступ, не триггерит файрвол/антивирус)
WEBUI_HOST = os.getenv("WEBUI_HOST", "127.0.0.1")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", 8001))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Обновление данных (секунды)
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 30))