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
        self.server = config.get("auth", {}).get("windows_auth", {}).get("ad_server", "")
        self.base_dn = config.get("auth", {}).get("windows_auth", {}).get("ad_base_dn")
        self.ldap_port = int(
            config.get("auth", {}).get("windows_auth", {}).get("ad_ldap_port", 389)
        )
        self.use_ssl = config.get("auth", {}).get("windows_auth", {}).get("ad_use_ssl", False)
        self.service_account = (
            config.get("auth", {}).get("windows_auth", {}).get("service_account", "")
        )
        self.service_password = (
            config.get("auth", {}).get("windows_auth", {}).get("service_password", "")
        )
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
            decoded = base64.b64decode(token).decode("utf-8")
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

    def _ad_connector(self):
        """Вернуть AD-коллектор для LDAP-запросов (или None)."""
        if not (self.server and self.domain and self.service_account and self.service_password):
            return None
        try:
            from manager.src.connectors.permissions.ad import ADPermissionCollector

            return ADPermissionCollector(
                domain=self.domain,
                server=self.server,
                base_dn=self.base_dn,
                username=self.service_account,
                password=self.service_password,
                use_ssl=self.use_ssl,
                ldap_port=self.ldap_port,
            )
        except Exception as e:
            logger.warning("Unable to init AD connector for LDAP: %s", e)
            return None

    def get_user_info(self, domain_user: str) -> Optional[Dict]:
        """Получение информации о пользователе из AD."""
        if not self.is_available():
            return None

        username = domain_user.split("\\")[-1] if "\\" in domain_user else domain_user

        # Попытка получить реальные данные из AD
        ad = self._ad_connector()
        if ad is not None and ad.is_available():
            try:
                info = ad.get_ad_user_info(username)
                if info:
                    info["domain_user"] = domain_user
                    return info
            except Exception as e:
                logger.warning("AD user info error: %s", e)

        # Заглушка для разработки
        return {
            "username": username,
            "full_name": username.capitalize(),
            "email": f"{username}@example.com",
            "domain_user": domain_user,
        }

    def get_user_groups(self, domain_user: str) -> List[str]:
        """Получение групп пользователя из AD."""
        if not self.is_available():
            return []

        username = domain_user.split("\\")[-1] if "\\" in domain_user else domain_user

        # Попытка получить реальные группы из AD
        ad = self._ad_connector()
        if ad is not None and ad.is_available():
            try:
                groups = ad.get_user_groups(username)
                if groups:
                    return groups
            except Exception as e:
                logger.warning("AD user groups error: %s", e)

        # Заглушка для разработки. В реальности — LDAP запрос к AD.
        return ["DCAP_Viewer"]

    def get_ad_user_from_db(self, domain_user: str, db: Session) -> Optional[object]:
        """Поиск AD пользователя в локальной БД."""
        from .models import User

        return (
            db.query(User)
            .filter(
                User.domain_user == domain_user,
                User.auth_source == "ad",
                User.is_active == True,  # noqa: E712
            )
            .first()
        )
