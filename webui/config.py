import os
import json
from pathlib import Path

VERSION = os.getenv("VERSION", "3.13.3")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("WEBUI_CONFIG", BASE_DIR / "config" / "config.json"))


def load_config() -> dict:
    """Загрузка конфига. Если файла нет — возвращает дефолты."""
    defaults = {
        "server": {"host": "127.0.0.1", "port": 8001},
        "manager": {"url": "http://127.0.0.1:8000"},
        "database": {"url": "sqlite:///manager/dcap.db"},
        "logging": {"level": "INFO"},
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            # Глубокое слияние с дефолтами
            defaults.update({k: v for k, v in data.items() if isinstance(v, dict)})
            cfg_version = data.get("version")
            if isinstance(cfg_version, str) and cfg_version.strip() and os.getenv("VERSION") is None:
                defaults["version"] = cfg_version.strip()
        except (ValueError, OSError):
            pass
    return defaults


_config = load_config()

# Версия (W-43): VERSION env → config.json version → default.
VERSION = os.getenv("VERSION") or _config.get("version") or VERSION

# Сервер
WEBUI_HOST = os.getenv("WEBUI_HOST", _config.get("server", {}).get("host", "127.0.0.1"))
WEBUI_PORT = int(os.getenv("WEBUI_PORT", _config.get("server", {}).get("port", 8001)))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Manager
MANAGER_URL = os.getenv("MANAGER_URL", _config.get("manager", {}).get("url", "http://127.0.0.1:8000"))

# База данных (SQLAlchemy URL)
DATABASE_URL = os.getenv("DATABASE_URL", _config.get("database", {}).get("url", "sqlite:///manager/dcap.db"))

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", _config.get("logging", {}).get("level", "INFO"))

# Обновление данных (секунды)
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 30))
