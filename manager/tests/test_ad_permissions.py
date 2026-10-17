# manager/tests/test_ad_permissions.py
"""
Unit-тесты AD-интеграции (День 33).
Тесты используют моки ldap3 — реальный DC не требуется.
Запуск: python -m pytest manager/tests/test_ad_permissions.py -v
"""

import sys
import time
from unittest import mock
from pathlib import Path

_MANAGER_SRC = str(Path(__file__).resolve().parents[1] / "src")

# BUG-259: scanner/connectors/filesystem.py импортирует top-level `connectors`,
# из-за чего в combined-прогоне (tests/unit + manager/tests) sys.modules
# ['connectors'] может указывать на scanner/connectors без subpackage
# `permissions`. Чистим коллизию и ставим manager/src первым.
for _name in [m for m in sys.modules if m == "connectors" or m.startswith("connectors.")]:
    del sys.modules[_name]
if _MANAGER_SRC in sys.path:
    sys.path.remove(_MANAGER_SRC)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, _MANAGER_SRC)

from connectors.permissions import (
    ADPermissionCollector,
    MixedPermissionCollector,
    PermissionCollectorFactory,
    ADCache,
)


# ============================================================
# ADCache
# ============================================================

class TestADCache:
    def test_memory_cache_set_get(self):
        cache = ADCache(ttl=300)
        cache.set("foo", {"a": 1})
        assert cache.get("foo") == {"a": 1}

    def test_memory_cache_expire(self):
        cache = ADCache(ttl=0)  # TTL 0 → сразу протухает
        cache.set("foo", "bar")
        assert cache.get("foo") is None

    def test_cache_miss(self):
        cache = ADCache(ttl=300)
        assert cache.get("missing") is None

    def test_invalidate(self):
        cache = ADCache(ttl=300)
        cache.set("k", "v")
        assert cache.get("k") == "v"
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_clear(self):
        cache = ADCache(ttl=300)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_redis_unavailable_falls_back(self):
        # Redis недоступен → используем memory-кэш, без исключений
        cache = ADCache(ttl=300, redis_url="redis://localhost:6390/0")
        assert cache.redis is not None  # клиент создаётся
        cache.set("x", [1, 2])
        # Redis не отвечает → fallback на memory
        assert cache.get("x") == [1, 2]


# ============================================================
# ADPermissionCollector (мок ldap3)
# ============================================================

def make_fake_connection():
    """Фейковое ldap3-подключение для тестов"""
    conn = mock.MagicMock()
    conn.bound = True
    conn.entries = []
    return conn


class FakeEntry:
    def __init__(self, dn, attrs):
        self.entry_dn = dn
        for k, v in attrs.items():
            setattr(self, k, mock.Mock(value=v))


def test_ad_collector_requires_password():
    """Без пароля коллектор недоступен"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        c = ADPermissionCollector(domain="SAMDOM", server="localhost")
        assert not c.is_available()


def test_ad_collector_connect_success():
    """Успешное подключение → коллектор доступен"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            fake_server = mock.Mock()
            fake_ldap.Server.return_value = fake_server
            fake_conn = mock.Mock()
            fake_conn.bound = True
            fake_ldap.Connection.return_value = fake_conn

            c = ADPermissionCollector(
                domain="SAMDOM",
                server="dc.samdom.example.com",
                username="administrator",
                password="Passw0rd",
            )
            assert c.is_available()
            assert c.connection is fake_conn

            # Проверка параметров подключения
            _, kwargs = fake_ldap.Server.call_args
            assert kwargs["connect_timeout"] == c.timeout

            _, conn_kwargs = fake_ldap.Connection.call_args
            assert conn_kwargs["user"] == "administrator@SAMDOM.EXAMPLE.COM"
            assert conn_kwargs["password"] == "Passw0rd"
            assert conn_kwargs["authentication"] == fake_ldap.SIMPLE


def test_resolve_principal():
    """Разрешение SID → доменное имя"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            entry = FakeEntry(
                "CN=Петров Василий,CN=Users,DC=SAMDOM,DC=EXAMPLE,DC=COM",
                {"sAMAccountName": "v.petrov"},
            )
            fake_conn = mock.Mock()
            fake_conn.bound = True
            fake_conn.entries = [entry]

            c = ADPermissionCollector(
                domain="SAMDOM",
                server="dc.samdom.example.com",
                username="administrator",
                password="Passw0rd",
            )
            c.connection = fake_conn
            c.ensure_connected = mock.Mock()

            name = c.resolve_principal("S-1-5-21-111-512")
            assert name == "SAMDOM\\v.petrov"

            # Фильтр должен содержать бинарный objectSid в LDAP-нотации
            args = fake_conn.search.call_args
            search_filter = args[0][1] if args[0] else args[1].get("search_filter", "")
            assert "(objectSid=" in search_filter


def test_get_user_groups():
    """Получение групп пользователя через AD"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            fake_conn = mock.Mock()
            fake_conn.bound = True

            # 1-й поиск: DN пользователя; 2-й поиск: группы
            search_results = [
                [
                    FakeEntry(
                        "CN=Смирнов Алексей,CN=Users,DC=SAMDOM,DC=EXAMPLE,DC=COM",
                        {"sAMAccountName": "a.smirnov"},
                    )
                ],
                [
                    FakeEntry("CN=DCAP_Auditors,CN=Users,DC=SAMDOM,DC=EXAMPLE,DC=COM",
                              {"sAMAccountName": "DCAP_Auditors"}),
                ],
            ]

            def fake_search(*args, **kwargs):
                if search_results:
                    fake_conn.entries = search_results.pop(0)
                else:
                    fake_conn.entries = []
                return True

            fake_conn.search = mock.Mock(side_effect=fake_search)

            c = ADPermissionCollector(
                domain="SAMDOM",
                server="localhost",
                username="administrator",
                password="Passw0rd",
            )
            c.connection = fake_conn
            c.ensure_connected = mock.Mock()

            groups = c.get_user_groups("SAMDOM\\a.smirnov")
            assert "DCAP_Auditors" in groups


def test_get_principal_groups_delegates():
    """get_principal_groups → get_user_groups"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            fake_conn = mock.Mock()
            fake_conn.bound = True
            fake_conn.search = mock.Mock(side_effect=lambda *a, **k: fake_conn.__setattr__("entries", []))
            fake_ldap.Connection.return_value = fake_conn

            c = ADPermissionCollector(
                domain="SAMDOM", server="localhost",
                username="administrator", password="Passw0rd",
            )
            c.connection = fake_conn
            c.ensure_connected = mock.Mock()

            assert c.get_principal_groups("SAMDOM\\user") == []


def test_get_principals_types():
    """Список субъектов: ad_group + ad_user"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            results = [
                [FakeEntry("CN=G1,CN=Users,DC=SAMDOM,DC=EXAMPLE,DC=COM",
                           {"sAMAccountName": "G1"})],
                [FakeEntry("CN=U1,CN=Users,DC=SAMDOM,DC=EXAMPLE,DC=COM",
                           {"sAMAccountName": "U1"})],
            ]

            fake_conn = mock.Mock()
            fake_conn.bound = True

            def fake_search(*args, **kwargs):
                if results:
                    fake_conn.entries = results.pop(0)
                else:
                    fake_conn.entries = []
                return True

            fake_conn.search = mock.Mock(side_effect=fake_search)

            c = ADPermissionCollector(
                domain="SAMDOM", server="localhost",
                username="administrator", password="Passw0rd",
            )
            c.connection = fake_conn
            c.ensure_connected = mock.Mock()

            principals = c.get_principals()
            types = {p["type"] for p in principals}
            assert "ad_group" in types
            assert "ad_user" in types
            assert all(p["domain"] == "SAMDOM" for p in principals)


def test_collect_fallback_to_local_on_nonwindows():
    """На Linux без smbcacls происходит fallback на local сбор"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            fake_conn = mock.Mock()
            fake_conn.bound = True
            fake_conn.search = mock.Mock()
            fake_ldap.Connection.return_value = fake_conn

            with mock.patch("connectors.permissions.ad.ADPermissionCollector._is_windows",
                            return_value=False):
                with mock.patch("connectors.permissions.ad.ADPermissionCollector._get_acl_linux") as m_acl:
                    m_acl.return_value = [
                        {"sid": "S-1-5-21-000-512",
                         "permissions": ["full_control"],
                         "inherited": False}
                    ]
                    # resolve_principal через _lookup_sid вернёт None → principal = sid
                    c = ADPermissionCollector(
                        domain="SAMDOM", server="localhost",
                        username="administrator", password="Passw0rd",
                    )
                    c._lookup_sid = mock.Mock(return_value=(None, None))
                    entries = c.collect("\\share\\Data")
                    assert len(entries) == 1
                    assert entries[0]["collector_source"] == "ad"
                    assert entries[0]["permissions"] == ["full_control"]


def test_check_permission():
    """Проверка права: прямая выдача + через группу"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            fake_conn = mock.Mock()
            fake_conn.bound = True
            fake_ldap.Connection.return_value = fake_conn

            c = ADPermissionCollector(
                domain="SAMDOM", server="localhost",
                username="administrator", password="Passw0rd",
            )
            # Мокаем collect → запись для группы DCAP_Auditors (read)
            c.collect = mock.Mock(return_value=[
                {"principal": "SAMDOM\\DCAP_Auditors",
                 "principal_type": "ad_group",
                 "permissions": ["read"],
                 "is_inherited": False,
                 "collector_source": "ad"},
            ])
            c.get_user_groups = mock.Mock(return_value=["DCAP_Auditors"])

            assert c.check_permission("\\\\share\\Reports", "SAMDOM\\a.smirnov", "read") is True
            assert c.check_permission("\\\\share\\Reports", "SAMDOM\\a.smirnov", "write") is False


def test_mixed_collector_falls_back_to_local():
    """Mixed: при недоступности AD — local-сбор"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        with mock.patch("connectors.permissions.ad.ldap3") as fake_ldap:
            fake_ldap.Connection.side_effect = Exception("no DC")
            c = MixedPermissionCollector(ad_kwargs={
                "domain": "SAMDOM", "server": "localhost",
                "username": "administrator", "password": "Passw0rd",
            })
            assert c.is_available() is True
            assert c.get_source_type() == "mixed"


def test_factory_ad_unknown_on_missing_dc():
    """get_collector('ad') без DC → RuntimeError"""
    with mock.patch("connectors.permissions.ad.HAS_LDAP3", True):
        # Симитируем неуспешное подключение к AD
        with mock.patch("connectors.permissions.ad.ADPermissionCollector._connect",
                        return_value=False):
            with mock.patch("manager.src.services.access_config.get_access_config") as m_cfg:
                from manager.src.services.access_config import ADConfig
                m_cfg.return_value.mode = "local"
                m_cfg.return_value.ad = ADConfig(
                    server="localhost", domain="SAMDOM",
                    username="administrator", password="secret",
                )
                try:
                    PermissionCollectorFactory.get_collector("ad")
                    assert False, "должен быть RuntimeError"
                except RuntimeError:
                    pass