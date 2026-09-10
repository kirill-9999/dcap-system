# manager/src/core/rate_limit.py
"""Rate limiting с Redis (приоритет) и in-memory fallback (fail-open).

Используется для общих /api/* через RateLimitMiddleware. Поведение:
- Redis доступен — счётчики в Redis (INCR + EXPIRE).
- Redis недоступен/отключён — локальный словарь (по процессу) либо
  fail-open (пропуск) при недоступности обоих механизмов.
"""
import logging
import time
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..cache.redis_client import get_redis

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self, max_requests: int = 300, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._local: Dict[str, List[float]] = defaultdict(list)

    def _redis_key(self, key: str) -> str:
        return f"rl:{key}"

    def check(self, key: str) -> bool:
        """True — запрос разрешён, False — превышен лимит (429)."""
        redis = get_redis()
        if redis.available:
            count = redis.increment(self._redis_key(key), ttl=self.window_seconds)
            if count < 0:
                # Redis потерял связь между ping и incr — fallback
                pass
            else:
                return count <= self.max_requests

        # In-memory fallback
        now = time.time()
        cutoff = now - self.window_seconds
        attempts = [t for t in self._local.get(key, []) if t > cutoff]
        if len(attempts) >= self.max_requests:
            return False
        attempts.append(now)
        self._local[key] = attempts
        return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Применение лимита ко всем /api/* запросам (кроме health)."""

    def __init__(
        self,
        app,
        max_requests: int = 300,
        window_seconds: int = 60,
        whitelist: Optional[List[str]] = None,
    ):
        super().__init__(app)
        self.limiter = RateLimiter(max_requests, window_seconds)
        self.whitelist = set(whitelist or [])

    def _key(self, request: Request) -> str:
        client = request.client.host if request.client else "unknown"
        if request.state and getattr(request.state, "client_cert_cn", None):
            client = f"{client}:{request.state.client_cert_cn}"
        return client

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/") or path in self.whitelist or path == "/api/health":
            return await call_next(request)

        if not self.limiter.check(self._key(request)):
            return Response(
                content='{"detail":"Too many requests"}',
                status_code=429,
                media_type="application/json",
            )

        return await call_next(request)