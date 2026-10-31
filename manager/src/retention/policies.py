# manager/src/retention/policies.py
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

DEFAULTS = {
    "audit_events": {"ttl_days": 90, "archive_ttl_days": 365, "archive_enabled": True},
    "findings": {"ttl_days": 180},
    "tasks": {"ttl_days": 30},
    "logs": {"rotate_days": 30, "max_size_mb": 100},
}


class RetentionPolicy:
    """Политика хранения для каждого типа данных."""

    def __init__(self, config: dict):
        self.config = config
        self._policies: Dict[str, dict] = {}
        self._load_policies()

    def _load_policies(self):
        """Загрузка политик из конфига."""
        retention_config = self.config.get("retention", {})

        self._policies = {}
        for data_type, defaults in DEFAULTS.items():
            section = retention_config.get(data_type, {}) or {}
            policy = dict(DEFAULTS[data_type])
            policy.update({k: v for k, v in section.items() if v is not None})
            self._policies[data_type] = policy

        logger.info(f"Loaded retention policies: {list(self._policies.keys())}")

    def get_policy(self, data_type: str) -> Optional[dict]:
        """Получение полной политики для типа данных."""
        return self._policies.get(data_type)

    def get_ttl(self, data_type: str) -> Optional[int]:
        """Получение TTL (срок хранения) для типа данных."""
        policy = self._policies.get(data_type)
        if policy:
            return policy.get("ttl_days")
        return None

    def get_cutoff_date(self, data_type: str) -> Optional[datetime]:
        """Получение даты отсечения для типа данных."""
        ttl = self.get_ttl(data_type)
        if ttl is not None:
            return datetime.utcnow() - timedelta(days=ttl)
        return None

    def get_archive_ttl(self) -> int:
        """Срок хранения архивных событий (audit_events.archive_ttl_days)."""
        return int(self._policies.get("audit_events", {}).get("archive_ttl_days", 365))

    def archive_enabled(self) -> bool:
        """Разрешена ли архивация аудит-событий."""
        return bool(self._policies.get("audit_events", {}).get("archive_enabled", True))
