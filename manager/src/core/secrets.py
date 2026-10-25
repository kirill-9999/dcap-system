"""SecretsManager: управление секретами (Docker Secrets → env → default)."""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Ключи шифрования находок (День 40.1)
FINDINGS_KEYS = [
    "findings_encryption_key",
    "findings_hmac_key",
    "findings_key_id",
]


class SecretsManager:
    """Единая точка доступа к секретам.

    Приоритет: Docker Secrets (/run/secrets/) → env vars → default.
    """

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.secrets_dir = Path(config.get("secrets_dir", "/run/secrets"))
        self.cache: Dict[str, Optional[str]] = {}

    def get(self, key: str, default: Any = None) -> Optional[str]:
        """Получить секрет по ключу.

        Docker Secrets: файл /run/secrets/<key> (без подчёркиваний, lowercase).
        Env var: полное имя ключа.
        """
        if key in self.cache:
            return self.cache[key]

        # 1. Docker Secrets
        secret_name = key.lower().replace("_", "")
        secret_path = self.secrets_dir / secret_name
        if secret_path.exists():
            try:
                value = secret_path.read_text(encoding="utf-8").strip()
                self.cache[key] = value
                return value
            except Exception as e:
                # key — имя секрета (например, FINDINGS_ENCRYPTION_KEY), e — исключение;
                # значение секрета НЕ логируется.
                logger.debug("Error reading Docker secret %s: %s", key, e)  # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure

        # 2. Environment variables
        value = os.environ.get(key)
        if value is not None:
            self.cache[key] = value
            return value

        # 3. Default
        self.cache[key] = default
        return default

    def get_required(self, key: str) -> str:
        """Получить обязательный секрет. Если не найден — ValueError."""
        value = self.get(key)
        if value is None:
            raise ValueError(f"Required secret not found: {key}")
        return value

    def has(self, key: str) -> bool:
        """Проверить, доступен ли секрет."""
        return self.get(key) is not None

    def load_all(self, keys: Dict[str, Any]) -> Dict[str, Optional[str]]:
        """Массовая загрузка секретов.

        keys: {KEY_NAME: default_value, ...}
        Возвращает: {KEY_NAME: resolved_value, ...}
        """
        result = {}
        for key, default in keys.items():
            result[key] = self.get(key, default)
        return result


# Глобальный экземпляр (ленивая инициализация)
_instance: Optional[SecretsManager] = None


def get_secrets_manager(config: Optional[dict] = None) -> SecretsManager:
    global _instance
    if _instance is None:
        _instance = SecretsManager(config)
    return _instance
