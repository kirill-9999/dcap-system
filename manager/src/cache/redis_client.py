# manager/src/cache/redis_client.py
"""Redis-клиент Manager (кэш, сессии, rate-limit, отложенные задачи).

Использует redis-py с graceful-fallback: если Redis недоступен или не
сконфигурирован, все операции возвращают значения по умолчанию (No-op
режим), чтобы Manager продолжал работать без брокера.

Конфигурация берётся из config.json секции `redis`:
    "redis": {
        "url": "redis://localhost:6379/0",
        "password": "${REDIS_PASSWORD:-}",
        "enabled": true,
        "cache_ttl": 300
    }

Env-переменные: REDIS_URL, REDIS_PASSWORD, REDIS_ENABLED.
"""
import json
import logging
from typing import Any, Optional

from ..config import get_config

logger = logging.getLogger(__name__)


class RedisClient:
    def __init__(
        self,
        url: Optional[str] = None,
        enabled: Optional[bool] = None,
        cache_ttl: int = 300,
        redis_module: Any = None,
    ):
        self._redis_module = redis_module
        self._client = None
        self.cache_ttl = cache_ttl

        cfg = get_config().get("redis", {})
        self.url = url or cfg.get("url", "redis://localhost:6379/0")
        self.password = cfg.get("password") or None
        cfg_enabled = cfg.get("enabled", True)
        if isinstance(cfg_enabled, str):
            cfg_enabled = cfg_enabled.strip().lower() in ("1", "true", "yes", "on")
        self.enabled = enabled if enabled is not None else cfg_enabled
        self._connect()

    def _connect(self) -> None:
        if not self.enabled:
            logger.debug("Redis disabled in config — no-op mode")
            return
        try:
            if self._redis_module is None:
                import redis  # noqa: PLC0415

                self._redis_module = redis
            kwargs = {
                "url": self.url,
                "decode_responses": True,
                "socket_timeout": 3,
                "socket_connect_timeout": 3,
                "retry_on_timeout": True,
            }
            if self.password:
                kwargs["password"] = self.password
            self._client = self._redis_module.Redis.from_url(**kwargs)
            self._client.ping()
            logger.info(f"Redis connected: {self.url}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Redis unavailable ({e}) — no-op mode")
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    def get(self, key: str) -> Optional[str]:
        if not self.available:
            return None
        try:
            return self._client.get(key)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Redis get failed: {e}")
            return None

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        if not self.available:
            return False
        try:
            self._client.set(key, value, ex=ttl or self.cache_ttl)
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Redis set failed: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self.available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Redis delete failed: {e}")
            return False

    def get_json(self, key: str) -> Any:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            return None

    def set_json(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            return self.set(key, json.dumps(value, ensure_ascii=False), ttl)
        except (TypeError, ValueError):
            return False

    # --- Rate limit / счетчики ---
    def increment(self, key: str, amount: int = 1, ttl: int = 60) -> int:
        """INCR с истечением. Возвращает -1 при недоступности Redis."""
        if not self.available:
            return -1
        try:
            val = self._client.incr(key, amount)
            if val == amount:
                self._client.expire(key, ttl)
            return int(val)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Redis incr failed: {e}")
            return -1

    # --- Очереди (День 39, метрики Celery) ---
    def llen(self, queue: str) -> int:
        """Размер очереди Celery (LLEN). Возвращает -1 при недоступности Redis."""
        if not self.available:
            return -1
        try:
            return int(self._client.llen(queue)) if hasattr(self._client, "llen") else -1
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Redis llen failed: {e}")
            return -1


_redis_client: Optional[RedisClient] = None


def get_redis() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client


def reset_redis_client() -> None:
    global _redis_client
    _redis_client = None