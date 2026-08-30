# manager/src/auth/jwt.py
import os
from datetime import datetime, timedelta
from typing import Optional, Dict

import jwt

ALGORITHM = "HS256"


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
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=self.access_ttl_minutes)
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)

    def create_refresh_token(self, data: Dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_ttl_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)

    def verify_token(self, token: str) -> Optional[Dict]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

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
