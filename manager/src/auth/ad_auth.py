# manager/src/auth/ad_auth.py
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

try:
    import ldap3

    HAS_LDAP3 = True
except ImportError:  # pragma: no cover
    ldap3 = None
    HAS_LDAP3 = False


class ADAuthenticator:
    """Явный логин пользователя через Active Directory (LDAP bind по паролю).

    Подключается как сам пользователь (bind) для проверки пароля,
    затем (при необходимости) возвращает информацию о пользователе и группах.
    """

    def __init__(self, config: dict):
        """
        Args:
            config: dict с ключами:
                enabled                  — включать ли AD-логин
                ad_domain                — NETBIOS-домен (SAMDOM)
                ad_server                — адрес контроллера домена
                ad_base_dn               — базовый DN (опционально)
                ad_ldap_port             — порт LDAP (по умолчанию 389)
                ad_use_ssl               — использовать LDAPS
                ad_service_account       — служебная учётка (не обязательна для bind-логина)
                ad_service_password      — её пароль
        """
        ad_cfg = (
            config.get("auth", {}).get("windows_auth", {}) if "auth" in config else (config or {})
        )
        self.enabled = ad_cfg.get("enabled", False) or bool(ad_cfg.get("ad_server"))
        self.domain = ad_cfg.get("ad_domain", "")
        self.server = ad_cfg.get("ad_server", "localhost")
        self.base_dn = ad_cfg.get("ad_base_dn") or ad_cfg.get("base_dn")
        self.ldap_port = int(ad_cfg.get("ad_ldap_port", 389))
        self.use_ssl = ad_cfg.get("ad_use_ssl", False)
        self.service_account = (
            ad_cfg.get("ad_service_account") or ad_cfg.get("service_account") or ""
        )
        self.service_password = (
            ad_cfg.get("ad_service_password") or ad_cfg.get("service_password") or ""
        )
        self.timeout = int(ad_cfg.get("ad_timeout", 10))

        self._available = bool(self.enabled and HAS_LDAP3 and self.server and self.domain)

    def is_available(self) -> bool:
        return self._available

    @staticmethod
    def _upn(domain: str, username: str) -> str:
        """Формирование UPN-имени для LDAP-bind."""
        username = username.split("\\")[-1].strip()
        d = domain.strip().upper()
        if "." not in d:
            d = f"{d}.EXAMPLE.COM"
        return f"{username}@{d}"

    def _new_connection(self, user: str, password: str):
        """Создать LDAP-соединение с указанными креденшелами."""
        server = ldap3.Server(
            self.server,
            port=self.ldap_port,
            use_ssl=self.use_ssl,
            connect_timeout=self.timeout,
        )
        return ldap3.Connection(
            server,
            user=user,
            password=password,
            authentication=ldap3.SIMPLE,
            auto_bind=True,
            receive_timeout=self.timeout,
        )

    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """Проверить AD-учётку по паролю.

        Возвращает информацию о пользователе (username, full_name, email,
        domain_user, groups) или None при неудачной проверке.
        """
        if not self.is_available():
            logger.info("AD authenticator not available")
            return None
        if not username or not password:
            return None

        username_clean = username.split("\\")[-1].strip()

        try:
            # Bind самим пользователем — проверка пароля
            conn = self._new_connection(self._upn(self.domain, username_clean), password)
        except Exception as e:
            logger.warning("AD bind failed for %s: %s", username_clean, e)
            return None

        try:
            info = self._fetch_user_info(conn, username_clean)
            info["domain_user"] = f"{self.domain}\\{username_clean}"
            info["auth_source"] = "ad"
            return info
        except Exception as e:
            logger.error("Error fetching AD user info for %s: %s", username_clean, e)
            return None
        finally:
            try:
                conn.unbind()
            except Exception:
                pass

    def _default_base_dn(self) -> str:
        if self.base_dn:
            return self.base_dn
        parts = self.domain.strip().upper().split(".")
        return ",".join(f"DC={p}" for p in parts)

    def get_user_groups(self, conn, username: str) -> List[str]:
        """Получить список групп пользователя (прямое членство)."""
        groups: List[str] = []
        base_dn = self._default_base_dn()

        try:
            # DN пользователя
            conn.search(
                base_dn,
                f"(&(objectClass=user)(sAMAccountName={username}))",
                attributes=["distinguishedName"],
                size_limit=1,
            )
            if not conn.entries:
                return groups
            user_dn = conn.entries[0].entry_dn

            # Группы, где пользователь в member
            conn.search(
                base_dn,
                f"(&(objectClass=group)(member={user_dn}))",
                attributes=["sAMAccountName"],
                size_limit=200,
            )
            for entry in conn.entries:
                name = getattr(entry, "sAMAccountName", None)
                gname = getattr(name, "value", None) if name else None
                if gname:
                    groups.append(gname)
        except Exception as e:
            logger.warning("Error getting AD groups for %s: %s", username, e)

        return groups

    def _fetch_user_info(self, conn, username: str) -> Dict:
        """Получить атрибуты пользователя и группы."""
        base_dn = self._default_base_dn()

        full_name = None
        email = None

        conn.search(
            base_dn,
            f"(&(objectClass=user)(objectCategory=person)(sAMAccountName={username}))",
            attributes=["displayName", "mail", "sAMAccountName", "userPrincipalName", "cn"],
            size_limit=1,
        )
        if conn.entries:
            entry = conn.entries[0]

            def _v(attr):
                a = getattr(entry, attr, None)
                return getattr(a, "value", None) if a else None

            display = _v("displayName") or _v("cn")
            full_name = display
            email = _v("mail")

        groups = self.get_user_groups(conn, username)

        return {
            "username": username,
            "full_name": full_name or username.capitalize(),
            "email": email,
            "groups": groups,
        }
