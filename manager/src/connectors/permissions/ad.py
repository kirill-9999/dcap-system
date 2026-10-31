# manager/src/connectors/permissions/ad.py

"""
Коллектор прав доступа через Active Directory (День 33).

Реализует интерфейс PermissionCollector (как local/remote), а также
AD-специфичные методы:
- resolve_principal(sid) — разрешение SID в доменное имя
- check_permission(...)  — проверка наличия права у пользователя
- get_user_groups(...)   — список групп пользователя

Источники прав:
- Windows: win32security (DACL) для NTFS
- Linux/Samba: smbcacls (с fallback на локальный сбор)
"""

import logging
import platform
import re
from typing import List, Dict, Optional, Any

from .base import PermissionCollector
from .cache import ADCache

logger = logging.getLogger(__name__)

try:
    import ldap3
    HAS_LDAP3 = True
except ImportError:  # pragma: no cover
    ldap3 = None
    HAS_LDAP3 = False


class ADPermissionCollector(PermissionCollector):
    """Коллектор прав доступа через Active Directory"""

    def __init__(
        self,
        domain: Optional[str] = None,
        server: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        base_dn: Optional[str] = None,
        use_ssl: bool = False,
        ldap_port: int = 389,
        timeout: int = 10,
        cache_ttl: int = 300,
        redis_url: Optional[str] = None,
    ):
        """Параметры подключения к контроллеру домена.

        Если параметры не заданы (None), берутся из дефолтов (для тестов
        с Samba DC по умолчанию) либо из фабрики (из access_config).
        """
        self.domain = (domain or "SAMDOM").strip()
        self.server = server or "localhost"
        self.username = username or "administrator"
        self.password = password or ""
        self.base_dn = base_dn or self._default_base_dn(self.domain)
        self.use_ssl = use_ssl
        self.ldap_port = ldap_port
        self.timeout = timeout

        self._source_type = "ad"
        self._available = False
        self.connection: Optional[Any] = None

        # Кэширование
        self.cache = ADCache(ttl=cache_ttl, redis_url=redis_url)

        # Локальные кэши
        self.sid_cache: Dict[str, Optional[str]] = {}
        self.group_membership_cache: Dict[str, List[str]] = {}

        # Проверяем доступность (мягко — без проброса исключений)
        if self.server and self.domain:
            self._available = self._connect()

    # ============================================================
    # Подключение
    # ============================================================

    @staticmethod
    def _default_base_dn(domain: str) -> str:
        """Сформировать base_dn из домена (SAMDOM.EXAMPLE.COM → DC=SAMDOM,DC=EXAMPLE,DC=COM)"""
        parts = domain.strip().upper().split(".")
        if len(parts) == 1 and "." not in domain:
            # Дом в формате NETBIOS (SAMDOM) — не можем вывести полный DN,
            # оставляем как есть (пользователь переопределит через base_dn)
            return f"DC={domain.upper()}"
        return ",".join(f"DC={p}" for p in parts)

    def _connect(self) -> bool:
        """Установить соединение с AD"""
        if not HAS_LDAP3:
            logger.error("ldap3 не установлен — AD-коллектор недоступен")
            return False

        if not self.password:
            logger.error("AD-коллектор требует пароль служебной учётной записи")
            return False

        try:
            server = ldap3.Server(
                self.server,
                port=self.ldap_port,
                use_ssl=self.use_ssl,
                connect_timeout=self.timeout,
                get_info=ldap3.NONE,
            )

            domain_upn = self.domain.upper()
            if "." not in domain_upn:
                # NETBIOS-дом → UPN вида SAMDOM.EXAMPLE.COM (как в Samba DC)
                domain_upn = f"{domain_upn}.EXAMPLE.COM"

            self.connection = ldap3.Connection(
                server,
                user=f"{self.username}@{domain_upn}",
                password=self.password,
                authentication=ldap3.SIMPLE,
                auto_bind=True,
                receive_timeout=self.timeout,
            )

            logger.info("Connected to AD: %s (%s)", self.server, self.base_dn)
            return True

        except Exception as e:
            logger.error("AD connection failed (%s): %s", self.server, e)
            self.connection = None
            return False

    def ensure_connected(self) -> None:
        """Проверить соединение, переподключить при необходимости"""
        if self.connection is None or not getattr(self.connection, "bound", False):
            if not self._connect():
                raise ConnectionError(
                    f"Cannot connect to AD: {self.server} (check credentials/network)"
                )
        else:
            # Проверка живости соединения
            try:
                self.connection.search(
                    self.base_dn, "(objectClass=*)", search_scope=ldap3.BASE, size_limit=0
                )
            except Exception:
                if not self._connect():
                    raise ConnectionError(
                        f"Cannot reconnect to AD: {self.server}"
                    )

    # ============================================================
    # Интерфейс PermissionCollector
    # ============================================================

    def collect(self, resource_path: str) -> List[Dict]:
        """Собрать NTFS-права через AD (универсальный формат, как в local.py)"""
        self.ensure_connected()

        cache_key = f"access:{resource_path}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.debug("AD collect: cache hit for %s", resource_path)
            return cached

        entries: List[Dict] = []

        try:
            if self._is_windows():
                acl_data = self._get_acl_windows(resource_path)
            else:
                acl_data = self._get_acl_linux(resource_path)

            for ace in acl_data:
                sid = ace.get("sid")
                principal = self.resolve_principal(sid) or sid or ace.get("principal") or "unknown"
                principal_type = self._get_principal_type(sid) if sid else self._guess_principal_type(principal)

                entries.append({
                    "principal": principal,
                    "principal_type": principal_type,
                    "principal_sid": sid,
                    "principal_domain": self._extract_domain(principal),
                    "permissions": ace.get("permissions", []),
                    "is_inherited": ace.get("inherited", False),
                    "inherited_from": "parent" if ace.get("inherited") else None,
                    "collector_source": "ad",
                })

            self.cache.set(cache_key, entries)

        except Exception as e:
            logger.error("Error getting AD permissions for %s: %s", resource_path, e)
            # Fallback на локальный сбор прав
            from .local import LocalPermissionCollector
            logger.warning("AD collect: falling back to local icacls for %s", resource_path)
            local = LocalPermissionCollector()
            entries = local.collect(resource_path)
            for entry in entries:
                entry["collector_source"] = "ad_fallback"

        return entries

    def get_effective_permissions(self, resource_path: str, principal: str) -> List[str]:
        """Эффективные права пользователя через AD (прямые + группы)"""
        try:
            entries = self.collect(resource_path)
        except Exception as e:
            logger.error("get_effective_permissions: %s", e)
            return []

        user_name = principal.split("\\")[-1]
        permissions = set()

        # Прямые права пользователя
        for entry in entries:
            entry_name = (entry.get("principal") or "").split("\\")[-1]
            if entry_name.lower() == user_name.lower():
                permissions.update(entry.get("permissions", []))
                if "full_control" in entry.get("permissions", []):
                    permissions.add("full_control")

        # Права через группы
        try:
            groups = self.get_user_groups(principal)
        except Exception:
            groups = []

        for entry in entries:
            entry_name = (entry.get("principal") or "").split("\\")[-1]
            if any(g.lower() == entry_name.lower() for g in groups):
                permissions.update(entry.get("permissions", []))
                if "full_control" in entry.get("permissions", []):
                    permissions.add("full_control")

        return list(permissions)

    def get_principals(self) -> List[Dict]:
        """Получить список пользователей и групп из AD"""
        self.ensure_connected()
        principals: List[Dict] = []

        # Группы
        self.connection.search(
            self.base_dn,
            "(objectClass=group)",
            attributes=["sAMAccountName", "distinguishedName"],
            size_limit=500,
        )
        for entry in self.connection.entries:
            name = getattr(entry, "sAMAccountName", None)
            name = name.value if name else None
            if name:
                principals.append({
                    "name": name,
                    "type": "ad_group",
                    "domain": self.domain,
                    "sid": None,
                })

        # Пользователи
        self.connection.search(
            self.base_dn,
            "(&(objectClass=user)(objectCategory=person))",
            attributes=["sAMAccountName"],
            size_limit=500,
        )
        for entry in self.connection.entries:
            name = getattr(entry, "sAMAccountName", None)
            name = name.value if name else None
            if name:
                principals.append({
                    "name": name,
                    "type": "ad_user",
                    "domain": self.domain,
                    "sid": None,
                })

        return principals

    def get_principal_groups(self, principal: str) -> List[str]:
        """Получить группы AD, в которых состоит пользователь (для AccessService)"""
        try:
            return self.get_user_groups(principal)
        except Exception as e:
            logger.error("get_principal_groups: %s", e)
            return []

    def get_source_type(self) -> str:
        return "ad"

    def is_available(self) -> bool:
        return self._available

    # ============================================================
    # AD-специфичные методы
    # ============================================================

    def resolve_principal(self, sid: str) -> Optional[str]:
        """Разрешить SID в доменное имя (пользователь/группа)"""
        if not sid:
            return None

        # Локальный кэш
        if sid in self.sid_cache:
            return self.sid_cache[sid]

        # Redis-кэш
        cache_key = f"sid:{sid}"
        cached = self.cache.get(cache_key)
        if cached:
            self.sid_cache[sid] = cached
            return cached

        try:
            self.ensure_connected()

            # LDAP не умеет искать по строковому SID напрямую в общем случае —
            # ищем по sIDHistory/sAMAccountName через поиск по objectSid (raw).
            dn, full_name = self._lookup_sid(sid)
            if full_name:
                self.sid_cache[sid] = full_name
                self.cache.set(cache_key, full_name)
                return full_name

            return None

        except Exception as e:
            logger.error("Error resolving SID %s: %s", sid, e)
            return None

    def _lookup_sid(self, sid: str):
        """Поиск объекта в AD по SID. Возвращает (dn, имя) или (None, None).

        objectSid в AD хранится в бинарном виде, поэтому строковый SID
        конвертируем в бинарный и фильтруем по (objectSid=...).
        """
        if not sid.startswith("S-"):
            return None, None

        binary_sid = self._sid_to_binary(sid)
        if not binary_sid:
            return None, None

        # LDAP-фильтр для бинарного значения: \XX\XX...
        ldap_binary = "".join(f"\\{b:02X}" for b in binary_sid)
        search_filter = f"(objectSid={ldap_binary})"

        try:
            self.connection.search(
                self.base_dn,
                search_filter,
                attributes=["sAMAccountName", "name"],
                search_scope=ldap3.SUBTREE,
                size_limit=1,
            )
            if self.connection.entries:
                entry = self.connection.entries[0]
                name_attr = getattr(entry, "sAMAccountName", None) or getattr(entry, "name", None)
                name = getattr(name_attr, "value", None) if name_attr else None
                if name:
                    full_name = f"{self.domain}\\{name}"
                    return entry.entry_dn, full_name
        except Exception as e:
            logger.debug("SID lookup error: %s", e)

        return None, None

    @staticmethod
    def _sid_to_binary(sid: str):
        """Конвертировать SDDL SID (S-1-5-21-...) в бинарный bytes.

        Формат: Revision(1) + SubAuthorityCount(1) + IdentifierAuthority(6)
                + SubAuthority(N * 4, little-endian)
        """
        try:
            parts = sid.split("-")
            if len(parts) < 3 or parts[0].upper() != "S":
                return None

            revision = int(parts[1])
            sub_auths = [int(p) for p in parts[3:]] if len(parts) > 3 else []

            # IdentifierAuthority: 6 байт big-endian (из 2-байтного или 4-байтного числа)
            ia_value = int(parts[2])
            if ia_value <= 0xFFFF:
                ia_bytes = bytes([0, 0, 0, 0]) + ia_value.to_bytes(2, "big")
            else:
                ia_bytes = ia_value.to_bytes(6, "big")

            result = bytearray()
            result.append(revision)
            result.append(len(sub_auths))
            result.extend(ia_bytes)
            for sa in sub_auths:
                result.extend(sa.to_bytes(4, "little", signed=False))

            return bytes(result)
        except Exception as e:
            logger.debug("SID parse error (%s): %s", sid, e)
            return None

    def _get_principal_type(self, sid: str) -> str:
        """Определить тип principal (user/group) по SID"""
        try:
            binary_sid = self._sid_to_binary(sid) if sid and sid.startswith("S-") else None
            if binary_sid:
                ldap_binary = "".join(f"\\{b:02X}" for b in binary_sid)
                self.connection.search(
                    self.base_dn,
                    f"(objectSid={ldap_binary})",
                    attributes=["objectClass"],
                    size_limit=1,
                )
                if self.connection.entries:
                    oc = getattr(self.connection.entries[0], "objectClass", None)
                    classes = getattr(oc, "value", []) if oc else []
                    if "group" in classes:
                        return "ad_group"
                    return "ad_user"
        except Exception:
            pass

        # Fallback: RID 512/513/... → группа
        if sid and re.search(r"-\d{3,5}$", sid):
            rid = int(sid.rsplit("-", 1)[1])
            if rid in (512, 513, 514, 515, 516, 517, 518, 519, 520, 521, 1104):
                return "ad_group"
        return "ad_user"

    @staticmethod
    def _guess_principal_type(principal: str) -> str:
        """Определить тип по имени (fallback, если нет SID)"""
        p = (principal or "").lower()
        if "domain users" in p or "domain admins" in p or p.endswith("group"):
            return "ad_group"
        return "ad_user"

    @staticmethod
    def _extract_domain(principal: str) -> Optional[str]:
        if "\\" in principal:
            return principal.split("\\")[0]
        return None

    def get_user_groups(self, user: str) -> List[str]:
        """Получить список AD-групп пользователя (с кэшированием)"""
        self.ensure_connected()

        username = user.split("\\")[-1].strip()
        if not username:
            return []

        if username in self.group_membership_cache:
            return self.group_membership_cache[username]

        groups: List[str] = []

        try:
            # 1) Находим DN пользователя
            self.connection.search(
                self.base_dn,
                f"(&(objectClass=user)(sAMAccountName={self._escape_filter(username)}))",
                attributes=["distinguishedName"],
                size_limit=1,
            )
            if not self.connection.entries:
                return []

            user_dn = self.connection.entries[0].entry_dn

            # 2) Ищем группы, где user числится в member (прямое членство)
            self.connection.search(
                self.base_dn,
                f"(&(objectClass=group)(member={self._escape_filter(user_dn)}))",
                attributes=["sAMAccountName"],
                size_limit=100,
            )
            for entry in self.connection.entries:
                name = getattr(entry, "sAMAccountName", None)
                gname = getattr(name, "value", None) if name else None
                if gname:
                    groups.append(gname)

            self.group_membership_cache[username] = groups

        except Exception as e:
            logger.error("Error getting user groups for %s: %s", username, e)
            groups = []

        return groups

    def get_ad_user_info(self, username: str) -> Optional[Dict]:
        """Получить информацию о пользователе AD (имя, email, группы).

        Возвращает None при недоступности/ошибке.
        """
        try:
            self.ensure_connected()
        except Exception:
            return None

        username = username.split("\\")[-1].strip()
        full_name = None
        email = None

        try:
            self.connection.search(
                self.base_dn,
                f"(&(objectClass=user)(objectCategory=person)"
                f"(sAMAccountName={self._escape_filter(username)}))",
                attributes=["displayName", "mail", "cn"],
                size_limit=1,
            )
            if self.connection.entries:
                entry = self.connection.entries[0]
                for attr in ("displayName", "cn"):
                    a = getattr(entry, attr, None)
                    v = getattr(a, "value", None) if a else None
                    if v:
                        full_name = v
                        break
                m = getattr(entry, "mail", None)
                email = getattr(m, "value", None) if m else None
        except Exception as e:
            logger.debug("get_ad_user_info lookup error: %s", e)

        try:
            groups = self.get_user_groups(username)
        except Exception:
            groups = []

        return {
            "username": username,
            "full_name": full_name or username.capitalize(),
            "email": email,
            "groups": groups,
        }

    @staticmethod
    def _escape_filter(value: str) -> str:
        """Экранирование LDAP-фильтра"""
        return (
            value.replace("\\", "\\5c")
            .replace("*", "\\2a")
            .replace("(", "\\28")
            .replace(")", "\\29")
            .replace("\x00", "\\00")
        )

    def check_permission(self, resource_path: str, user: str, permission: str) -> bool:
        """Проверить наличие права у пользователя на ресурс"""
        entries = self.collect(resource_path)
        user_name = user.split("\\")[-1]

        # Прямые права
        for entry in entries:
            entry_name = (entry.get("principal") or "").split("\\")[-1]
            if entry_name.lower() == user_name.lower():
                if permission in entry.get("permissions", []) or "full_control" in entry.get("permissions", []):
                    return True

        # Права через группы
        try:
            groups = self.get_user_groups(user)
        except Exception:
            groups = []

        for entry in entries:
            entry_name = (entry.get("principal") or "").split("\\")[-1]
            if any(g.lower() == entry_name.lower() for g in groups):
                if permission in entry.get("permissions", []) or "full_control" in entry.get("permissions", []):
                    return True

        return False

    # ============================================================
    # Сбор NTFS-прав (Windows/Linux)
    # ============================================================

    def _get_acl_windows(self, resource_path: str) -> List[dict]:
        """Windows: используем win32security для получения DACL"""
        import win32security
        import ntsecuritycon
        import win32file  # noqa: F401

        result: List[dict] = []
        try:
            sd = win32security.GetFileSecurity(
                resource_path,
                win32security.DACL_SECURITY_INFORMATION,
            )
            dacl = sd.GetSecurityDescriptorDacl()
            if dacl is None:
                return result

            for i in range(dacl.GetAceCount()):
                try:
                    ace = dacl.GetAce(i)
                    sid = ace[2]

                    try:
                        name, domain, _ = win32security.LookupAccountSid(None, sid)
                        principal = f"{domain}\\{name}"
                    except Exception:
                        principal = str(sid)

                    permissions = []
                    mask = ace[1]
                    if mask & ntsecuritycon.FILE_GENERIC_READ:
                        permissions.append("read")
                    if mask & ntsecuritycon.FILE_GENERIC_WRITE:
                        permissions.append("write")
                    if mask & ntsecuritycon.FILE_DELETE:
                        permissions.append("delete")
                    if mask & ntsecuritycon.FILE_GENERIC_ALL:
                        permissions.append("full_control")

                    if permissions:
                        result.append({
                            "sid": str(sid),
                            "principal": principal,
                            "permissions": permissions,
                            "inherited": bool(ace[1] & ntsecuritycon.OBJECT_INHERIT_ACE),
                        })
                except Exception as e:
                    logger.debug("Error processing ACE: %s", e)

        except Exception as e:
            logger.error("Error getting ACL on Windows: %s", e)
            raise

        return result

    def _get_acl_linux(self, resource_path: str) -> List[dict]:
        """Linux: используем smbcacls (Samba) с fallback на локальный сбор"""
        import subprocess

        try:
            result = subprocess.run(
                ["smbcacls", f"//localhost/{resource_path.lstrip('/')}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return self._parse_smbcacls(result.stdout)
        except Exception:
            pass

        # Fallback: локальный сбор через getfacl/icacls
        from .local import LocalPermissionCollector
        local = LocalPermissionCollector()
        entries = local.collect(resource_path)
        return [
            {
                "sid": e.get("principal"),
                "principal": e.get("principal"),
                "permissions": e.get("permissions", []),
                "inherited": e.get("is_inherited", False),
            }
            for e in entries
        ]

    @staticmethod
    def _parse_smbcacls(output: str) -> List[dict]:
        """Парсинг вывода smbcacls"""
        result: List[dict] = []
        for line in output.splitlines():
            if not line or ":" not in line:
                continue
            parts = line.strip().split(":", 1)
            if len(parts) != 2:
                continue
            principal = parts[0].strip()
            perms = parts[1].strip()

            permissions = []
            if "READ" in perms or "READ_LIST" in perms:
                permissions.append("read")
            if "WRITE" in perms or "WRITE_DATA" in perms:
                permissions.append("write")
            if "DELETE" in perms:
                permissions.append("delete")
            if "FULL" in perms or "FULL_CONTROL" in perms:
                permissions.append("full_control")

            result.append({
                "sid": principal,
                "principal": principal,
                "permissions": permissions,
                "inherited": False,
            })
        return result

    @staticmethod
    def _is_windows() -> bool:
        return platform.system() == "Windows"


class MixedPermissionCollector(PermissionCollector):
    """Смешанный коллектор: собирает права из AD, при недоступности AD —
    падает на локальный сбор (icacls). Режим 'mixed'."""

    def __init__(self, ad_kwargs: Optional[Dict[str, Any]] = None):
        self.ad_kwargs = dict(ad_kwargs or {})
        self._source_type = "mixed"
        self._available = True  # mixed всегда "доступен" — использует local как fallback

        # AD коллектор (может быть недоступен)
        try:
            self.ad = ADPermissionCollector(**self.ad_kwargs)
        except Exception as e:
            logger.warning("MixedPermissionCollector: AD init failed: %s", e)
            self.ad = None

        # Local коллектор (fallback)
        from .local import LocalPermissionCollector
        self.local = LocalPermissionCollector()

    # ------------------------------------------------------------
    # Интерфейс
    # ------------------------------------------------------------

    def collect(self, resource_path: str) -> List[Dict]:
        """Сбор прав: сначала AD, при недоступности/ошибке — local."""
        try:
            if self.ad is not None and self.ad.is_available():
                return self.ad.collect(resource_path)
        except Exception as e:
            logger.warning("Mixed collect via AD failed (%s), falling back to local", e)

        return self.local.collect(resource_path)

    def get_effective_permissions(self, resource_path: str, principal: str) -> List[str]:
        try:
            if self.ad is not None and self.ad.is_available():
                return self.ad.get_effective_permissions(resource_path, principal)
        except Exception:
            pass
        return self.local.get_effective_permissions(resource_path, principal)

    def get_principals(self) -> List[Dict]:
        principals: List[Dict] = []
        try:
            if self.ad is not None and self.ad.is_available():
                principals.extend(self.ad.get_principals())
        except Exception:
            pass
        principals.extend(self.local.get_principals())
        return principals

    def get_principal_groups(self, principal: str) -> List[str]:
        try:
            if self.ad is not None and self.ad.is_available():
                return self.ad.get_principal_groups(principal)
        except Exception:
            pass
        return self.local.get_principal_groups(principal)

    def get_source_type(self) -> str:
        return "mixed"

    def resolve_principal(self, sid: str) -> Optional[str]:
        """Разрешить SID → доменное имя (делегирование в AD-коллектор)"""
        try:
            if self.ad is not None and self.ad.is_available():
                return self.ad.resolve_principal(sid)
        except Exception as e:
            logger.warning("Mixed resolve_principal failed (%s): %s", sid, e)
        return None

    def is_available(self) -> bool:
        return True
