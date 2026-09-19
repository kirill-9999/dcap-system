# manager/src/auth/jwt.py
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from uuid import uuid4

import jwt

ALGORITHM = "HS256"

logger = logging.getLogger(__name__)


class JWTManager:
    """Создание и верификация JWT токенов."""

    def __init__(self, secret_key: Optional[str] = None,
                 access_ttl_minutes: int = 1440,
                 refresh_ttl_days: int = 7):
        self.secret_key = secret_key or get_secret_key()
        self.access_ttl_minutes = access_ttl_minutes
        self.refresh_ttl_days = refresh_ttl_days

    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        now = datetime.utcnow()
        expire = now + (
            expires_delta or timedelta(minutes=self.access_ttl_minutes)
        )
        # TASK-013 (BUG-041): jti (UUID) + iat (UTC) для revocation на logout/refresh.
        to_encode.update({"exp": expire, "iat": now, "jti": str(uuid4()), "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)

    def create_refresh_token(self, data: Dict) -> str:
        to_encode = data.copy()
        now = datetime.utcnow()
        expire = now + timedelta(days=self.refresh_ttl_days)
        to_encode.update({"exp": expire, "iat": now, "jti": str(uuid4()), "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)

    def verify_token(self, token: str, expected_type: str = "access") -> Optional[Dict]:
        """Верификация JWT с проверкой типа токена (BUG-039).

        BUG-039: refresh-токен принимался в /me, /check и всех access-эндпоинтах.
        Теперь payload["type"] должен совпадать с expected_type (по умолчанию
        "access").
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        if payload.get("type") != expected_type:
            return None
        if self._is_blacklisted(payload.get("jti")):
            return None
        return payload

    def blacklist_jti(self, payload: Optional[Dict]) -> None:
        """Добавить jti токена в blacklist (Redis) на оставшийся TTL (TASK-013)."""
        if not payload or not payload.get("jti"):
            return
        try:
            from manager.src.cache.redis_client import get_redis  # noqa: PLC0415

            redis = get_redis()
            exp = payload.get("exp")
            ttl = int(exp) - int(datetime.utcnow().timestamp()) if exp else 3600
            if ttl <= 0:
                return
            redis.set(f"jwt-blacklist:{payload['jti']}", "1", ttl=ttl)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Blacklist jti failed: {e}")

    def _is_blacklisted(self, jti: Optional[str]) -> bool:
        if not jti:
            return False
        try:
            from manager.src.cache.redis_client import get_redis  # noqa: PLC0415

            redis = get_redis()
            return redis.get(f"jwt-blacklist:{jti}") is not None
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Blacklist check failed: {e}")
            return False

    def extract_user_id(self, token: str) -> Optional[int]:
        payload = self.verify_token(token)
        if payload and "user_id" in payload:
            return payload["user_id"]
        return None


def get_secret_key() -> str:
    """Получение секретного ключа из env (или дефолт для разработки)."""
    return os.environ.get("JWT_SECRET_KEY", "change-me-in-production-32-chars-long")


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    return JWTManager().create_access_token(data, expires_delta)


def create_refresh_token(data: Dict) -> str:
    return JWTManager().create_refresh_token(data)


def verify_token(token: str) -> Optional[Dict]:
    return JWTManager().verify_token(token)


def extract_user_id(token: str) -> Optional[int]:
    return JWTManager().extract_user_id(token)
