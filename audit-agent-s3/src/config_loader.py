# audit-agent-s3/src/config_loader.py
import json
import os
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """Загрузчик конфигурации с поддержкой переменных окружения.

    Поддерживает подстановку ${VAR} и ${VAR:-default} в значениях конфига.
    Проверяет наличие обязательных секций и параметров.
    """

    # Секции, обязательные для запуска
    REQUIRED_SECTIONS = ["agent", "s3", "manager", "buffer"]

    # Обязательные параметры внутри секций
    REQUIRED_KEYS = {
        "agent": ["name"],
        "s3": ["bucket", "access_key", "secret_key"],
        "manager": ["url"],
    }

    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self._validate()

    def _validate(self):
        """Валидация конфига."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        config = self.load()

        for section in self.REQUIRED_SECTIONS:
            if section not in config:
                raise ValueError(f"Missing required section: {section}")

        for section, keys in self.REQUIRED_KEYS.items():
            for key in keys:
                if section not in config or key not in config[section]:
                    raise ValueError(f"Missing required key: {section}.{key}")

    def load(self) -> Dict[str, Any]:
        """Загрузка конфига с подстановкой переменных окружения."""
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return self._substitute_env(config)

    def _substitute_env(self, obj):
        """Рекурсивная подстановка ${VAR} из окружения."""
        if isinstance(obj, dict):
            return {k: self._substitute_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env(v) for v in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var = obj[2:-1]
            # Поддержка значений по умолчанию: ${VAR:-default}
            if ":-" in var:
                var, default = var.split(":-", 1)
                return os.environ.get(var, default)
            return os.environ.get(var, obj)
        else:
            return obj
