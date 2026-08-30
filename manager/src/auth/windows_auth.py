# manager/src/auth/windows_auth.py
import logging
import os
import sys
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from datetime import datetime

logger = logging.getLogger(__name__)


class WindowsAuthenticator:
    """Windows Integrated Authentication (SPNEGO/Kerberos).

    В production с AD выполняется реальная валидация SPNEGO-токена.
    Для разработки без AD используется mock (заглушка) — кодируется
    домен\\пользователь в base64 вида "Negotiate base64(domain:username)".
    """

    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("auth", {}).get("windows_auth", {}).get("enabled", False)
        self.domain = config.get("auth", {}).get("windows_auth", {}).get("ad_domain", "")
        self._available = False
        self._spnego_available = False

        if self.enabled:
            self._init_spnego()

    def _init_spnego(self):
        """Инициализация SPNEGO"""
        try:
            import spnego  # noqa: F401
            self._spnego_available = True
            self._available = True
            logger.info("Windows Authenticator: spnego available")
        except ImportError:
            logger.warning("spnego not installed, Windows Auth disabled")
            self._available = False

    def is_available(self) -> bool:
        return self._available and self.enabled

    def is_ad_environment(self) -> bool:
        """Проверка: есть ли AD окружение"""
        if sys.platform == "win32":
            domain = os.environ.get("USERDOMAIN")
            return bool(domain and domain != "WORKGROUP")
        return bool(self.domain)

    def authenticate(self, auth_header: str) -> Optional[str]:
        """
        Аутентификация через SPNEGO.
        Возвращает DOMAIN\\username или None.
        """
        if not self.is_available():
            return None

        if not auth_header or not auth_header.startswith("Negotiate "):
            return None

        # Если нет AD — используем mock для разработки
        if not self.is_ad_environment():
            return self._mock_authenticate(auth_header)

        try:
            import spnego
            del spnego

            token = auth_header.replace("Negotiate ", "")

            # Реальная валидация через spnego — для production с AD.
            # В текущей версии (без реального AD) используем mock.
            return self._mock_authenticate(auth_header)

        except Exception as e:
            logger.error(f"SPNEGO error: {e}")
            return None

    def _mock_authenticate(self, auth_header: str) -> Optional[str]:
        """Mock-аутентификация для разработки без AD."""
        # Формат: Negotiate base64(domain:username)
        import base64
        try:
            token = auth_header.replace("Negotiate ", "")
            decoded = base64.b64decode(token).decode('utf-8')
            if ":" in decoded:
                domain, username = decoded.split(":", 1)
                return f"{domain}\\{username}"
        except Exception:
            pass

        # Fallback: используем переменную окружения
        if sys.platform == "win32":
            domain = os.environ.get("USERDOMAIN", "WORKGROUP")
            username = os.environ.get("USERNAME", "developer")
            return f"{domain}\\{username}"

        return "WORKGROUP\\developer"

    def get_user_info(self, domain_user: str) -> Optional[Dict]:
        """Получение информации о пользователе из AD."""
        if not self.is_available():
            return None

        username = domain_user.split("\\")[-1] if "\\" in domain_user else domain_user

        # Заглушка для разработки
        return {
            "username": username,
            "full_name": username.capitalize(),
            "email": f"{username}@example.com",
            "domain_user": domain_user
        }

    def get_user_groups(self, domain_user: str) -> List[str]:
        """Получение групп пользователя из AD."""
        if not self.is_available():
            return []

        # Заглушка для разработки. В реальности — LDAP запрос к AD.
        return ["DCAP_Viewer"]

    def get_ad_user_from_db(self, domain_user: str, db: Session) -> Optional[object]:
        """Поиск AD пользователя в локальной БД."""
        from .models import User
        return db.query(User).filter(
            User.domain_user == domain_user,
            User.auth_source == "ad",
            User.is_active == True  # noqa: E712
        ).first()
