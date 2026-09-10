# manager/src/config.py
"""Загрузчик конфигурации Manager (manager/config/config.json).

Слияние с дефолтами, поддержка env-переменных (JWT_SECRET_KEY, AUTH_MODE,
AD_DOMAIN, AD_SERVER, AD_SERVICE_USER, AD_SERVICE_PASSWORD).
"""
import os
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]  # manager/
CONFIG_PATH = Path(os.getenv("MANAGER_CONFIG", BASE_DIR / "config" / "config.json"))


def _resolve_env(value):
    """Разрешение ${VAR:-default} подстановок в строках конфига."""
    if not isinstance(value, str):
        return value
    if value.startswith("${") and value.endswith("}"):
        inner = value[2:-1]
        if ":-" in inner:
            var, default = inner.split(":-", 1)
            value = os.environ.get(var, default)
        else:
            value = os.environ.get(inner, value)
        # Нормализация булевых значений из env-переменных
        if isinstance(value, str):
            low = value.strip().lower()
            if low in ("true", "1", "yes"):
                return True
            if low in ("false", "0", "no"):
                return False
        return value
    return value


def _deep_merge(base, override):
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


_defaults = {
    "server": {"host": "127.0.0.1", "port": 8000},
    "database": {"url": "sqlite:///manager/dcap.db"},
    "redis": {
        "url": "${REDIS_URL:-redis://localhost:6379/0}",
        "password": "${REDIS_PASSWORD:-}",
        "enabled": "${REDIS_ENABLED:-true}",
        "cache_ttl": 300,
        "rate_limit": {"max_requests": 300, "window_seconds": 60},
    },
    "auth": {
        "mode": "${AUTH_MODE:-local}",
        "jwt_secret_key": "${JWT_SECRET_KEY:-change-me-in-production-32-chars-long}",
        "jwt_access_ttl_minutes": 1440,
        "jwt_refresh_ttl_days": 7,
        "bcrypt_rounds": 12,
        "local_users_enabled": True,
        "auto_create_ad_users": True,
        "default_role": "viewer",
        "windows_auth": {
            "enabled": False,
            "ad_domain": "${AD_DOMAIN:-}",
            "ad_server": "${AD_SERVER:-}",
            "ad_ldap_port": 389,
            "ad_use_ssl": False,
            "service_account": "${AD_SERVICE_USER:-}",
            "service_password": "${AD_SERVICE_PASSWORD:-}",
            "group_mapping": {
                "DCAP_Admin": "admin",
                "DCAP_Auditor": "auditor",
                "DCAP_Scanner": "scanner",
            },
        },
    },
    "webui": {"enabled": True, "host": "127.0.0.1", "port": 8001},
    "logging": {"level": "INFO"},
    "retention": {
        "enabled": True,
        "interval_hours": 24,
        "audit_events": {
            "ttl_days": 90,
            "archive_ttl_days": 365,
            "archive_enabled": True,
            "archive_table": "audit_logs_archive",
        },
        "findings": {
            "ttl_days": 180,
        },
        "tasks": {
            "ttl_days": 30,
        },
        "logs": {
            "rotate_days": 30,
            "max_size_mb": 100,
        },
        "export": {
            "enabled": True,
            "format": "json",
            "path": "data/archive/",
        },
    },
}


def load_config() -> dict:
    data = {}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (ValueError, OSError):
            data = {}

        def _resolve(obj):
            if isinstance(obj, dict):
                return {k: _resolve(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_resolve(v) for v in obj]
            return _resolve_env(obj)

        data = _resolve(data)

    config = _deep_merge(json.loads(json.dumps(_defaults)), data)

    # Разрешение env-подстановок в финальном конфиге (включая дефолты)
    def _final_resolve(obj):
        if isinstance(obj, dict):
            return {k: _final_resolve(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_final_resolve(v) for v in obj]
        return _resolve_env(obj)

    return _final_resolve(config)


_config = load_config()


def get_config() -> dict:
    return _config
