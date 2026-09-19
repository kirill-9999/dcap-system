import os
import json
from pathlib import Path

VERSION = os.getenv("VERSION", "3.13.7")

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("WEBUI_CONFIG", BASE_DIR / "config" / "config.json"))


def load_config() -> dict:
    """Р—Р°РіСЂСѓР·РєР° РєРѕРЅС„РёРіР°. Р•СЃР»Рё С„Р°Р№Р»Р° РЅРµС‚ вЂ” РІРѕР·РІСЂР°С‰Р°РµС‚ РґРµС„РѕР»С‚С‹."""
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
            # Р“Р»СѓР±РѕРєРѕРµ СЃР»РёСЏРЅРёРµ СЃ РґРµС„РѕР»С‚Р°РјРё
            defaults.update({k: v for k, v in data.items() if isinstance(v, dict)})
            cfg_version = data.get("version")
            if isinstance(cfg_version, str) and cfg_version.strip() and os.getenv("VERSION") is None:
                defaults["version"] = cfg_version.strip()
        except (ValueError, OSError):
            pass
    return defaults


_config = load_config()

# Р’РµСЂСЃРёСЏ (W-43): VERSION env в†’ config.json version в†’ default.
VERSION = os.getenv("VERSION") or _config.get("version") or VERSION

# РЎРµСЂРІРµСЂ
WEBUI_HOST = os.getenv("WEBUI_HOST", _config.get("server", {}).get("host", "127.0.0.1"))
WEBUI_PORT = int(os.getenv("WEBUI_PORT", _config.get("server", {}).get("port", 8001)))
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

# Manager
MANAGER_URL = os.getenv("MANAGER_URL", _config.get("manager", {}).get("url", "http://127.0.0.1:8000"))

# Р‘Р°Р·Р° РґР°РЅРЅС‹С… (SQLAlchemy URL)
DATABASE_URL = os.getenv("DATABASE_URL", _config.get("database", {}).get("url", "sqlite:///manager/dcap.db"))

# Р›РѕРіРёСЂРѕРІР°РЅРёРµ
LOG_LEVEL = os.getenv("LOG_LEVEL", _config.get("logging", {}).get("level", "INFO"))

# РћР±РЅРѕРІР»РµРЅРёРµ РґР°РЅРЅС‹С… (СЃРµРєСѓРЅРґС‹)
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 30))
