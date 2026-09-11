# manager/src/auth/rate_limit.py
import os
import time
from collections import defaultdict
from typing import Dict, List
from fastapi import HTTPException

# Простой in-memory rate limiter по ключу (IP имя пользователя).
# В production — заменить на Redis/более строгий механизм.
# Лимит настраивается через env (для тестов и высоконагруженных deploy).
_LOGIN_MAX_ATTEMPTS = int(os.getenv("AUTH_LOGIN_MAX_ATTEMPTS", "5"))
_LOGIN_WINDOW_SECONDS = int(os.getenv("AUTH_LOGIN_WINDOW_SECONDS", "60"))


class RateLimiter:
    def __init__(self, max_attempts: int = _LOGIN_MAX_ATTEMPTS, window_seconds: int = _LOGIN_WINDOW_SECONDS):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: Dict[str, List[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        """Проверка лимита. При превышении — HTTPException 429."""
        now = time.time()
        cutoff = now - self.window_seconds
        attempts = [t for t in self._attempts.get(key, []) if t > cutoff]

        if len(attempts) >= self.max_attempts:
            raise HTTPException(
                status_code=429,
                detail="Too many login attempts. Try again later."
            )

        attempts.append(now)
        self._attempts[key] = attempts

    def reset(self, key: str) -> None:
        self._attempts.pop(key, None)


login_limiter = RateLimiter()
