# manager/src/auth/local_auth.py
import bcrypt
import logging
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from .models import User, Role

logger = logging.getLogger(__name__)


class LocalAuthenticator:
    """Локальная аутентификация (JWT + Bcrypt)"""

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("auth", {}).get("local_users_enabled", True)
        self.bcrypt_rounds = config.get("auth", {}).get("bcrypt_rounds", 12)

    def authenticate(self, username: str, password: str, db: Session) -> Optional[User]:
        """Аутентификация по логину/паролю"""
        if not self.enabled:
            return None

        user = db.query(User).filter(
            User.username == username,
            User.auth_source == "local",
            User.is_active == True  # noqa: E712
        ).first()

        if not user:
            return None

        if not user.check_password(password):
            return None

        user.last_login = datetime.utcnow()
        db.commit()

        return user

    def create_user(self, db: Session, username: str, password: str, email: str = None,
                    full_name: str = None, roles: list = None) -> User:
        """Создание локального пользователя"""
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            auth_source="local",
            is_active=True
        )
        user.set_password(password)

        if roles:
            for role_name in roles:
                role = db.query(Role).filter(Role.name == role_name).first()
                if role:
                    user.roles.append(role)

        db.add(user)
        db.commit()
        db.refresh(user)
        return user
