import os

# База данных
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///manager/src/db/dcap.db"
)

# WebUI настройки
WEBUI_HOST = os.getenv("WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", 8001))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Обновление данных (секунды)
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 30))