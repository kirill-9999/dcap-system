# manager/src/connectors/permissions/cache.py

import json
import logging
from typing import Optional, Any
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

try:
    import redis
    HAS_REDIS = True
except ImportError:  # pragma: no cover
    redis = None
    HAS_REDIS = False


class ADCache:
    """Кэширование AD-запросов через Redis (с fallback на локальный кэш)"""

    def __init__(self, ttl: int = 300, redis_url: Optional[str] = None):
        """
        Args:
            ttl: Время жизни записей кэша (секунды)
            redis_url: URL Redis. Если None или недоступен — используется memory-кэш
        """
        self.ttl = ttl
        self.redis = None
        self.local_cache = {}

        # Локальный кэш хранит (value, timestamp) tuples
        if redis_url and HAS_REDIS:
            try:
                redis_kwargs = dict(decode_responses=True)
                self.redis = redis.Redis.from_url(redis_url, **redis_kwargs)
                # Проверяем подключение (лениво — не блокируем инициализацию)
                logger.info("AD Cache: Redis client created (%s)", redis_url)
            except Exception as e:
                logger.warning("AD Cache: Redis not available, using memory cache: %s", e)
                self.redis = None

    def get(self, key: str) -> Optional[Any]:
        """Получение значения из кэша"""
        if self.redis:
            try:
                value = self.redis.get(key)
                if value is not None:
                    return json.loads(value)
            except Exception as e:
                logger.debug("Redis get error: %s", e)

        # Fallback на локальный кэш
        if key in self.local_cache:
            data, timestamp = self.local_cache[key]
            if (datetime.utcnow() - timestamp) <= timedelta(seconds=self.ttl):
                return data
            # Просроченная запись — удаляем
            del self.local_cache[key]

        return None

    def set(self, key: str, value: Any) -> None:
        """Сохранение значения в кэш"""
        try:
            data = json.dumps(value, default=str)

            if self.redis:
                try:
                    self.redis.setex(key, self.ttl, data)
                    return
                except Exception as e:
                    logger.debug("Redis set error: %s", e)

            # Fallback на локальный кэш
            self.local_cache[key] = (value, datetime.utcnow())

        except Exception as e:
            logger.error("Cache set error: %s", e)

    def invalidate(self, key: str) -> None:
        """Инвалидация отдельного ключа"""
        if self.redis:
            try:
                self.redis.delete(key)
            except Exception:
                pass

        if key in self.local_cache:
            del self.local_cache[key]

    def clear(self) -> None:
        """Очистка всего кэша"""
        if self.redis:
            try:
                self.redis.flushdb()
            except Exception:
                pass

        self.local_cache.clear()
