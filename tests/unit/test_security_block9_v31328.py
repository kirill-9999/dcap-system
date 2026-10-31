# tests/unit/test_security_block9_v31328.py
# Фикс-спринт Блок 9 (v3.13.28) — юнит-тесты по всем 10 багам:
#   BUG-103 MetricsMiddleware (порядок + нормализация endpoint)
#   BUG-105 docker-compose volume сертификатов
#   BUG-106 machine-endpoint: _check_mtls больше не мёртвый код
#   BUG-107 CRL: verify_flags + is_revoked
#   BUG-108 run_manager.py через CertificateManager (+ ${VAR:-default})
#   BUG-110 reveal: 409 + аудит при ошибке расшифровки
#   BUG-111 _resolve_text: try/except
#   BUG-114 export-аудит: source_host + file_path
#   BUG-115 /api/findings/count: require_auth
#   BUG-116 reencrypt: пересчёт fingerprint + дедупликация
import importlib.util
import ssl
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from manager.src.db import models  # noqa: E402
from manager.src.db.session import get_db  # noqa: E402
from manager.src.auth.dependencies import get_current_user  # noqa: E402
from manager.src.api import findings as findings_api  # noqa: E402
from manager.src.core import security as security_mod  # noqa: E402
from manager.src.core.security import CertificateManager  # noqa: E402
from manager.src import metrics as metrics_mod  # noqa: E402

pytestmark = pytest.mark.unit


# ============================================================
# Общие фикстуры
# ============================================================

def _user(role: str = "admin"):
    """Простая заглушка User. has_role() нужен _is_auditor() в findings.py."""
    return SimpleNamespace(
        id=7,
        username=f"test_{role}",
        roles=[SimpleNamespace(name=role)],
        has_role=lambda r: r == role,
    )


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    """TestClient только на findings-роутере (без AuthMiddleware)."""
    app = FastAPI()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: _user("admin")
    app.include_router(findings_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _finding(db, **kw):
    """Создаёт Finding с дефолтами, достаточными для тестов."""
    base = dict(
        resource_id=1,
        finding_type="credentials",
        category="password",
        fragment_type="text_line",
        line_number=10,
        match_text_masked="pass****",
        line_text_masked="password = pass****",
        fingerprint="fp-existing",
        encryption_key_id="key-old",
    )
    base.update(kw)
    f = models.Finding(**base)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ============================================================
# BUG-115: /api/findings/count требует аутентификацию
# ============================================================

def test_bug115_count_requires_auth(client):
    """Без аутентификации /count обязан отдавать 401, а не данные."""
    app = client.app
    app.dependency_overrides.pop(get_current_user, None)
    r = client.get("/api/findings/count")
    assert r.status_code == 401


def test_bug115_count_authenticated_ok(client, db_session):
    """С аутентификацией /count отдаёт 200 и счётчик."""
    _finding(db_session)
    r = client.get("/api/findings/count")
    assert r.status_code == 200
    assert r.json()["count"] == 1


# ============================================================
# BUG-110: reveal отдаёт 409 (не 500) и аудирует неудачу
# ============================================================

def test_bug110_reveal_decrypt_failure_returns_409(client, db_session):
    """Битый ciphertext → 409 Conflict, а не 500 Internal Server Error."""
    f = _finding(db_session, match_text_encrypted="broken-ciphertext")
    r = client.post(f"/api/findings/{f.id}/reveal")
    assert r.status_code == 409
    assert "Decryption failed" in r.json()["detail"]


def test_bug110_reveal_failure_is_audited(client, db_session):
    """Неудачная попытка reveal попадает в audit_logs (event_type)."""
    f = _finding(db_session, match_text_encrypted="broken-ciphertext")
    client.post(f"/api/findings/{f.id}/reveal")
    logs = db_session.query(models.AuditLog).filter(
        models.AuditLog.event_type == "finding_reveal_failed"
    ).all()
    assert len(logs) == 1
    assert logs[0].metadata_json["finding_id"] == f.id
    assert logs[0].metadata_json["action"] == "finding_reveal_failed"


def test_bug110_reveal_success_still_200(client, db_session, monkeypatch):
    """Успешный reveal не сломан: 200 + finding_reveal в аудите."""
    from manager.src.core.encryption import FindingEncryption

    enc = FindingEncryption(key=b"N" * 32, hmac_key=b"N" * 32, key_id="key-old")
    monkeypatch.setattr(findings_api, "get_encryption", lambda: enc)

    f = _finding(db_session, match_text_encrypted=enc.encrypt("secret123"))
    r = client.post(f"/api/findings/{f.id}/reveal")
    assert r.status_code == 200
    assert r.json()["match_text"] == "secret123"

    logs = db_session.query(models.AuditLog).filter(
        models.AuditLog.event_type == "finding_reveal"
    ).all()
    assert len(logs) == 1


# ============================================================
# BUG-111: _resolve_text не бросает исключение
# ============================================================

def test_bug111_resolve_text_returns_masked_on_decrypt_error(monkeypatch):
    """Ошибка расшифровки → отдаётся masked, исключение не пробрасывается."""

    class _Boom:
        def decrypt(self, _):
            raise ValueError("Decryption failed")

    monkeypatch.setattr(findings_api, "get_encryption", lambda: _Boom())
    f = SimpleNamespace(id=1, match_text_masked="pass****",
                        match_text_encrypted="whatever")
    assert findings_api._resolve_text(f, "match_text", True) == "pass****"


def test_bug111_resolve_text_masked_mode_never_decrypts(monkeypatch):
    """В режиме без reveal расшифровка не вызывается вовсе."""

    class _Boom:
        def decrypt(self, _):
            raise AssertionError("decrypt не должен вызываться")

    monkeypatch.setattr(findings_api, "get_encryption", lambda: _Boom())
    f = SimpleNamespace(id=1, match_text_masked="***", match_text_encrypted="x")
    assert findings_api._resolve_text(f, "match_text", False) == "***"


def test_bug111_export_survives_broken_row(client, db_session, monkeypatch):
    """Экспорт не падает целиком, если одна строка не расшифровывается."""

    class _Boom:
        def decrypt(self, _):
            raise ValueError("Decryption failed")

    monkeypatch.setattr(findings_api, "get_encryption", lambda: _Boom())
    _finding(db_session, match_text_encrypted="broken", line_text_encrypted="broken")
    r = client.get("/api/findings/export", params={"format": "csv", "reveal": "true"})
    assert r.status_code == 200
    assert "pass" in r.text


# ============================================================
# BUG-114: аудит экспорта содержит source_host и file_path
# ============================================================

def test_bug114_export_audit_has_source_host_and_file_path(client, db_session):
    """В findings_exported должны быть IP источника и пути фрагментов."""
    _finding(db_session, fragment_path="C:/secret/a.env")
    _finding(db_session, fragment_path="C:/secret/b.env")

    r = client.get("/api/findings/export")
    assert r.status_code == 200

    log = db_session.query(models.AuditLog).filter(
        models.AuditLog.event_type == "findings_exported"
    ).one()
    assert log.source_host == "testclient"
    assert "C:/secret/a.env" in log.file_path
    assert "C:/secret/b.env" in log.file_path
    assert log.file_path != "/"


def test_bug114_export_audit_caps_file_path_length(client, db_session):
    """Больше 10 путей — схлопывается в список + счётчик (нет DoS)."""
    for i in range(15):
        _finding(db_session, fragment_path=f"C:/f/{i}.env")
    client.get("/api/findings/export")
    log = db_session.query(models.AuditLog).filter(
        models.AuditLog.event_type == "findings_exported"
    ).one()
    assert "more)" in log.file_path


# ============================================================
# BUG-103: нормализация endpoint в метриках
# ============================================================

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("/api/findings/12345", "/api/findings/{id}"),
        ("/api/findings/1/fragment", "/api/findings/{id}/fragment"),
        (
            "/api/audit/agents/dcap-audit-linux-HOST01",
            "/api/audit/agents/dcap-audit-linux-HOST01",
        ),
        (
            "/api/audit/agents/550e8400-e29b-41d4-a716-446655440000",
            "/api/audit/agents/{uuid}",
        ),
        ("/api/tasks/7", "/api/tasks/{id}"),
        ("/api/findings", "/api/findings"),
    ],
)
def test_bug103_normalize_endpoint(raw, expected):
    """Числовые ID → {id}, UUID → {uuid}; обычные сегменты не трогаются."""
    req = SimpleNamespace(scope={"path": raw}, url=SimpleNamespace(path=raw))
    assert metrics_mod._normalize_endpoint(req) == expected


def test_bug103_normalize_prefers_route_template():
    """Если роутер известен — берётся его шаблон (точнее regex-фолбэка)."""
    route = SimpleNamespace(path="/api/findings/{finding_id}/fragment")
    req = SimpleNamespace(scope={"path": "/api/findings/999/fragment", "route": route},
                          url=SimpleNamespace(path="/api/findings/999/fragment"))
    assert metrics_mod._normalize_endpoint(req) == "/api/findings/{finding_id}/fragment"


# ============================================================
# BUG-106: machine-endpoint доходит до _check_mtls
# ============================================================

def _middleware_with_cert_manager(cert_manager):
    from manager.src.auth.middleware import AuthMiddleware

    mw = AuthMiddleware(
        app=FastAPI(),
        auth_manager=SimpleNamespace(jwt=SimpleNamespace(
            verify_token=lambda *a, **k: None)),
        db_session_factory=None,
        cert_manager=cert_manager,
    )
    return mw


def test_bug106_machine_endpoint_not_public():
    """BUG-106: machine-prefixes не должны считаться публичными."""
    mw = _middleware_with_cert_manager(None)
    for path in (
        "/api/scanner/register",
        "/api/scanner/heartbeat",
        "/api/audit/agents/register",
        "/api/audit/events",
    ):
        assert mw._is_machine_endpoint(path) is True
        assert mw._is_public(path) is False, path


def test_bug106_public_endpoints_still_public():
    """Реально публичные эндпоинты остались публичными."""
    mw = _middleware_with_cert_manager(None)
    for path in ("/api/health", "/metrics", "/api/auth/login", "/api/root"):
        assert mw._is_public(path) is True, path


def test_bug106_strict_mtls_rejects_machine_without_cert():
    """strict: machine-endpoint без клиентского сертификата → 401."""
    cm = SimpleNamespace(is_available=True, strict=True, crl_path=Path("nonexistent"))
    mw = _middleware_with_cert_manager(cm)
    req = SimpleNamespace(scope={}, state=SimpleNamespace())
    resp = mw._check_mtls(req)
    assert resp is not None
    assert resp.status_code == 401


def test_bug106_relaxed_mtls_allows_machine_without_cert():
    """relaxed: machine-endpoint без сертификата проходит."""
    cm = SimpleNamespace(is_available=True, strict=False, crl_path=Path("nonexistent"))
    mw = _middleware_with_cert_manager(cm)
    req = SimpleNamespace(scope={}, state=SimpleNamespace())
    assert mw._check_mtls(req) is None


# ============================================================
# BUG-107: CRL реально проверяется
# ============================================================

@pytest.fixture()
def real_crl(tmp_path):
    """Настоящий (пустой) CRL, подписанный тестовым CA — как в scripts/generate_certs.py."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from datetime import datetime, timezone

    from shared.cert_utils import generate_ca_keypair

    ca_key_pem, ca_cert_pem = generate_ca_keypair(key_size=2048)
    ca_key = serialization.load_pem_private_key(ca_key_pem, password=None)
    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem, default_backend())
    now = datetime.now(timezone.utc)
    crl = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_cert.subject)
        .last_update(now)
        .next_update(now.replace(year=now.year + 1))
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    crl_dir = tmp_path / "crl"
    crl_dir.mkdir()
    crl_path = crl_dir / "crl.pem"
    crl_path.write_bytes(crl.public_bytes(serialization.Encoding.PEM))
    return crl_path


@pytest.fixture()
def full_pki(tmp_path):
    """Полный комплект PKI (CA + manager-сертификат) в tmp_path."""
    from shared.cert_utils import generate_ca_keypair, generate_component_keypair

    ca_key_pem, ca_cert_pem = generate_ca_keypair(key_size=2048)
    comp_cert_pem, comp_key_pem = generate_component_keypair(
        "manager", ca_key_pem, ca_cert_pem
    )
    for d in ("ca", "manager", "crl"):
        (tmp_path / d).mkdir()
    (tmp_path / "ca" / "ca.crt").write_bytes(ca_cert_pem)
    (tmp_path / "manager" / "manager.crt").write_bytes(comp_cert_pem)
    (tmp_path / "manager" / "manager.key").write_bytes(comp_key_pem)
    return tmp_path


def test_bug107_apply_crl_sets_verify_flag(tmp_path, real_crl):
    """Настоящий CRL подключается и включает VERIFY_CRL_CHECK_LEAF."""
    cm = CertificateManager({"mtls_enabled": True, "certs_dir": str(tmp_path)})
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    assert cm._apply_crl(ctx) is True
    assert ctx.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF


def test_bug107_apply_crl_absent_is_not_error(tmp_path):
    """Нет CRL (dev-режим) — это не ошибка, проверка просто выключена."""
    cm = CertificateManager({"mtls_enabled": True, "certs_dir": str(tmp_path)})
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    assert cm._apply_crl(ctx) is False


def test_bug107_apply_crl_corrupt_fails_open(tmp_path):
    """Битый CRL не роняет запуск — проверка отключается с предупреждением."""
    (tmp_path / "crl").mkdir()
    (tmp_path / "crl" / "crl.pem").write_bytes(b"not-a-crl-at-all")
    cm = CertificateManager({"mtls_enabled": True, "certs_dir": str(tmp_path)})
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    assert cm._apply_crl(ctx) is False
    assert not (ctx.verify_flags & ssl.VERIFY_CRL_CHECK_LEAF)


def test_bug107_check_mtls_rejects_revoked_cert(real_crl, monkeypatch):
    """Отозванный сертификат отклоняется _check_mtls (BUG-107)."""
    cm = SimpleNamespace(
        is_available=True, strict=False, crl_path=real_crl,
        is_revoked=lambda _der: True,
    )
    mw = _middleware_with_cert_manager(cm)
    ssl_obj = SimpleNamespace(
        getpeercert=lambda binary_form=False: (
            b"DERBYTES" if binary_form else {"subject": ((("commonName", "agent"),),)}
        )
    )
    transport = SimpleNamespace(get_extra_info=lambda _k: ssl_obj)
    req = SimpleNamespace(scope={"transport": transport}, state=SimpleNamespace())

    resp = mw._check_mtls(req)
    assert resp is not None
    assert resp.status_code == 401
    assert b"revoked" in resp.body.lower()


def test_bug107_check_mtls_accepts_valid_cert(real_crl):
    """Не отозванный сертификат проходит и кладёт CN в request.state."""
    cm = SimpleNamespace(
        is_available=True, strict=False, crl_path=real_crl,
        is_revoked=lambda _der: False,
    )
    mw = _middleware_with_cert_manager(cm)
    ssl_obj = SimpleNamespace(
        getpeercert=lambda binary_form=False: (
            b"DERBYTES" if binary_form else {"subject": ((("commonName", "scanner01"),),)}
        )
    )
    transport = SimpleNamespace(get_extra_info=lambda _k: ssl_obj)
    req = SimpleNamespace(scope={"transport": transport}, state=SimpleNamespace())

    assert mw._check_mtls(req) is None
    assert req.state.client_cert_cn == "scanner01"


def test_bug107_is_revoked_accepts_der(real_crl):
    """is_revoked() принимает DER (как отдаёт getpeercert(binary_form=True))."""
    cm = CertificateManager({"mtls_enabled": True,
                             "certs_dir": str(real_crl.parent.parent)})
    # Мусорный DER → is_revoked не должен бросать (fail-open на парсинге).
    assert cm.is_revoked(b"\x30\x82not-a-real-cert") is False


def test_bug107_is_revoked_empty_crl_returns_false(real_crl):
    """Пустой CRL (никого не отозвали) → False, без исключений."""
    cm = CertificateManager({"mtls_enabled": True,
                             "certs_dir": str(real_crl.parent.parent)})
    from shared.cert_utils import generate_component_keypair, generate_ca_keypair
    ca_key_pem, ca_cert_pem = generate_ca_keypair(key_size=2048)
    cert_pem, _ = generate_component_keypair("agent", ca_key_pem, ca_cert_pem)
    assert cm.is_revoked(cert_pem) is False


def test_bug107_to_pem_passthrough():
    """_to_pem не ломает уже-PEM (DER_cert_to_PEM_cert на PEM падает)."""
    pem = b"-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"
    assert security_mod._to_pem(pem) == pem
    assert security_mod._to_pem(b"") == b""


# ============================================================
# BUG-108: run_manager.py использует CertificateManager
# ============================================================

def test_bug108_run_manager_uses_cert_manager():
    """run_manager.py импортирует CertificateManager (единый источник TLS)."""
    _spec = importlib.util.spec_from_file_location(
        "run_manager_tz", ROOT / "run_manager.py"
    )
    rm = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rm)
    assert hasattr(rm, "CertificateManager")

    # Проверяем ИСПОЛНЯЕМЫЙ код через AST: ручная сборка TLS-параметров
    # (ssl_cert_reqs/ssl_keyfile/...) в вызовах возвращаться не должна.
    import ast

    src = (ROOT / "run_manager.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    kwargs_used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg:
                    kwargs_used.add(kw.arg)
    assert not (kwargs_used & {"ssl_cert_reqs", "ssl_keyfile", "ssl_certfile",
                                "ssl_ca_certs"}), kwargs_used
    # Сертификаты берутся из готового SSL-контекста CertificateManager.
    assert "ssl" in kwargs_used or 'uvicorn_kwargs["ssl"] = ssl_ctx' in src


def test_bug108_security_config_resolves_env_placeholders(monkeypatch):
    """${MTLS_ENABLED:-false} разрешается, иначе mTLS включался сам собой."""
    _spec = importlib.util.spec_from_file_location(
        "run_manager_tz2", ROOT / "run_manager.py"
    )
    rm = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rm)

    monkeypatch.delenv("MTLS_ENABLED", raising=False)
    monkeypatch.delenv("MTLS_STRICT", raising=False)
    monkeypatch.delenv("CERTS_DIR", raising=False)

    cfg = rm.build_security_config(
        {"security": {
            "mtls_enabled": "${MTLS_ENABLED:-false}",
            "mtls_strict": "${MTLS_STRICT:-false}",
            "certs_dir": "${CERTS_DIR:-certs}",
        }}
    )
    assert cfg["mtls_enabled"] is False
    assert cfg["mtls_strict"] is False
    assert cfg["certs_dir"] == "certs"


def test_bug108_env_overrides_config(full_pki, monkeypatch):
    """Явные ENV перекрывают config.json — источник истины один (CertificateManager)."""
    monkeypatch.setenv("MTLS_ENABLED", "true")
    monkeypatch.setenv("MTLS_STRICT", "true")
    monkeypatch.setenv("CERTS_DIR", str(full_pki))
    cm = CertificateManager({"mtls_enabled": False, "mtls_strict": False,
                              "certs_dir": "certs"})
    assert cm.enabled is True
    assert cm.strict is True
    assert cm.certs_dir == full_pki
    assert cm.is_available is True
    assert cm.get_server_ssl_context().verify_mode == ssl.CERT_REQUIRED


def test_bug108_env_absent_uses_config(monkeypatch):
    """Без ENV берётся значение из конфига (регрессия на дефолты)."""
    for v in ("MTLS_ENABLED", "MTLS_STRICT", "CERTS_DIR"):
        monkeypatch.delenv(v, raising=False)
    cm = CertificateManager({"mtls_enabled": False, "mtls_strict": False,
                              "certs_dir": "certs"})
    assert cm.enabled is False
    assert cm.strict is False
    assert str(cm.certs_dir) == "certs"


def test_bug108_strict_mode_uses_cert_required(full_pki):
    """strict → ssl.CERT_REQUIRED (BUG-108: strict был невозможен)."""
    relaxed = CertificateManager(
        {"mtls_enabled": True, "certs_dir": str(full_pki), "mtls_strict": False}
    ).get_server_ssl_context()
    strict = CertificateManager(
        {"mtls_enabled": True, "certs_dir": str(full_pki), "mtls_strict": True}
    ).get_server_ssl_context()

    assert relaxed is not None and strict is not None
    assert relaxed.verify_mode == ssl.CERT_OPTIONAL
    assert strict.verify_mode == ssl.CERT_REQUIRED
    assert strict.minimum_version == ssl.TLSVersion.TLSv1_2


# ============================================================
# BUG-105: docker-compose монтирует ./certs, а не manager/certs
# ============================================================

def test_bug105_compose_mounts_root_certs():
    """PKI лежит в ./certs (scripts/generate_certs.py), не в manager/certs."""
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Проверяем сами строки volume, а не комментарии.
    volumes = [
        ln.strip().lstrip("- ").strip() for ln in compose.splitlines()
        if ln.strip().startswith("- ./") and "certs" in ln
    ]
    assert "./certs:/app/certs:ro" in volumes
    assert not any(v.startswith("./manager/certs") for v in volumes)


def test_bug105_prod_override_consistent():
    """prod-override уже монтирует ./certs/* — базовый compose должен совпадать."""
    prod = (ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "./certs/manager:/app/certs/manager" in prod
    assert "./certs/ca:/app/certs/ca" in prod


# ============================================================
# BUG-116: пересчёт fingerprint + дедупликация
# ============================================================

def _load_reenc():
    _spec = importlib.util.spec_from_file_location(
        "reenc_block9", ROOT / "scripts" / "reencrypt_findings.py"
    )
    m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(m)
    return m


def _keys():
    from manager.src.core.encryption import FindingEncryption
    old = FindingEncryption(key=b"O" * 32, hmac_key=b"O" * 32, key_id="key-old")
    new = FindingEncryption(key=b"N" * 32, hmac_key=b"N" * 32, key_id="key-new")
    return old, new


def test_bug116_fingerprint_recalculated_with_new_hmac(db_engine):
    """FP пересчитывается новым HMAC-ключом (старый больше не остаётся)."""
    reenc = _load_reenc()
    old, new = _keys()
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        res = models.Resource(path="C:/data", type="filesystem")
        db.add(res)
        db.commit()
        db.refresh(res)
        rid = res.id
        _f = models.Finding(
            resource_id=rid, finding_type="credentials", category="password",
            fragment_type="text_line", line_number=42,
            match_text_encrypted=old.encrypt("s3cret"),
            fingerprint=old.fingerprint("C:/data", 42, "s3cret", "credentials"),
            encryption_key_id="key-old",
        )
        db.add(_f)
        db.commit()
        stale_fp = _f.fingerprint

    stats = reenc.run_reencrypt(db_engine, old, new)
    assert stats["fp_recalculated"] == 1
    expected = new.fingerprint("C:/data", 42, "s3cret", "credentials")

    with Session() as db:
        row = db.query(models.Finding).one()
        assert row.fingerprint == expected
        assert row.fingerprint != stale_fp
        assert new.decrypt(row.match_text_encrypted) == "s3cret"


def test_bug116_uses_resource_path_not_fragment_path(db_engine):
    """FP считается по Resource.path, а не по fragment_path (иначе FP разъезжается)."""
    reenc = _load_reenc()
    old, new = _keys()
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        res = models.Resource(path="C:/data", type="filesystem")
        db.add(res)
        db.commit()
        db.refresh(res)
        _f = models.Finding(
            resource_id=res.id, finding_type="credentials", category="password",
            fragment_type="text_line", line_number=7,
            fragment_path="C:/fragments/x.png",
            match_text_encrypted=old.encrypt("tok"),
            fingerprint="stale", encryption_key_id="key-old",
        )
        db.add(_f)
        db.commit()

    reenc.run_reencrypt(db_engine, old, new)
    with Session() as db:
        row = db.query(models.Finding).one()
        assert row.fingerprint == new.fingerprint("C:/data", 7, "tok", "credentials")


def test_bug116_dedup_marks_duplicate(db_engine):
    """--dedup помечает вторую копию status='duplicate' вместо дубля."""
    reenc = _load_reenc()
    old, new = _keys()
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        res = models.Resource(path="C:/data", type="filesystem")
        db.add(res)
        db.commit()
        db.refresh(res)
        for _ in range(2):
            db.add(models.Finding(
                resource_id=res.id, finding_type="credentials", category="password",
                fragment_type="text_line", line_number=5,
                match_text_encrypted=old.encrypt("dup"),
                fingerprint="stale", encryption_key_id="key-old",
            ))
        db.commit()

    stats = reenc.run_reencrypt(db_engine, old, new, dedup=True)
    assert stats["duplicates_found"] == 1
    assert stats["duplicates_marked"] == 1

    with Session() as db:
        rows = db.query(models.Finding).order_by(models.Finding.id).all()
        assert len(rows) == 2
        assert rows[1].status == "duplicate"


def test_bug116_delete_duplicates(db_engine):
    """--delete-duplicates удаляет дубль."""
    reenc = _load_reenc()
    old, new = _keys()
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        res = models.Resource(path="C:/data", type="filesystem")
        db.add(res)
        db.commit()
        db.refresh(res)
        for _ in range(2):
            db.add(models.Finding(
                resource_id=res.id, finding_type="credentials", category="password",
                fragment_type="text_line", line_number=5,
                match_text_encrypted=old.encrypt("dup"),
                fingerprint="stale", encryption_key_id="key-old",
            ))
        db.commit()

    stats = reenc.run_reencrypt(db_engine, old, new, delete_duplicates=True)
    assert stats["duplicates_deleted"] == 1
    with Session() as db:
        assert db.query(models.Finding).count() == 1


def test_bug116_dedup_disabled_by_default(db_engine):
    """Без флагов дедупликация выключена — скрипт ничего не удаляет."""
    reenc = _load_reenc()
    old, new = _keys()
    Session = sessionmaker(bind=db_engine)
    with Session() as db:
        res = models.Resource(path="C:/data", type="filesystem")
        db.add(res)
        db.commit()
        db.refresh(res)
        for _ in range(2):
            db.add(models.Finding(
                resource_id=res.id, finding_type="credentials", category="password",
                fragment_type="text_line", line_number=5,
                match_text_encrypted=old.encrypt("dup"),
                fingerprint="stale", encryption_key_id="key-old",
            ))
        db.commit()

    stats = reenc.run_reencrypt(db_engine, old, new)
    assert stats["duplicates_found"] == 0
    with Session() as db:
        assert db.query(models.Finding).count() == 2


def test_bug116_report_contains_new_counters(capsys):
    """Отчёт содержит новые счётчики FP и дедупликации."""
    reenc = _load_reenc()
    reenc.print_report({
        "total": 10, "already_new": 1, "reencrypted": 9, "skipped": 0,
        "batch_size": 500, "dry_run": False, "skipped_ids": [],
        "fp_recalculated": 9, "fp_unchanged": 0, "duplicates_found": 2,
        "duplicates_deleted": 1, "duplicates_marked": 0,
    })
    out = capsys.readouterr().out
    assert "FP recalculated:    9" in out
    assert "Duplicates deleted: 1" in out
