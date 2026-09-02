# manager/tests/test_security.py
"""
Тесты безопасности (День 34): CertificateManager (mTLS), SecretsManager,
генерация/проверка сертификатов, CRL.

Запуск: python -m pytest manager/tests/test_security.py -v
"""

import os
import sys
import ssl
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.cert_utils import (
    extract_cn,
    generate_ca_keypair,
    generate_component_keypair,
    validate_certificate,
    is_certificate_revoked,
)

from manager.src.core.secrets import SecretsManager, get_secrets_manager


# ============================================================
# FIXTURES (генерация тестовых сертификатов в tmp)
# ============================================================

@pytest.fixture(scope="module")
def pki(tmp_path_factory):
    """Сгенерировать CA + компонент в временной папке."""
    base = tmp_path_factory.mktemp("pki")
    ca_key_pem, ca_cert_pem = generate_ca_keypair(cn="DCAP-CA", valid_days=3650)

    cert_dir = base / "ca"
    cert_dir.mkdir(parents=True, exist_ok=True)
    (cert_dir / "ca.key").write_bytes(ca_key_pem)
    (cert_dir / "ca.crt").write_bytes(ca_cert_pem)

    # Компонент manager
    cert_pem, key_pem = generate_component_keypair(
        cn="manager.dcap.local",
        ca_key_pem=ca_key_pem,
        ca_cert_pem=ca_cert_pem,
        san="DNS:manager,DNS:localhost",
    )
    comp_dir = base / "manager"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "manager.crt").write_bytes(cert_pem)
    (comp_dir / "manager.key").write_bytes(key_pem)

    # Компонент agent-s3 (для CRL-теста)
    agent_cert_pem, _ = generate_component_keypair(
        cn="agent-s3",
        ca_key_pem=ca_key_pem,
        ca_cert_pem=ca_cert_pem,
    )
    agents_dir = base / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / "agent-s3.crt").write_bytes(agent_cert_pem)
    (agents_dir / "agent-s3.key").write_bytes(b"")

    return {
        "base": base,
        "ca_cert_pem": ca_cert_pem,
        "ca_key_pem": ca_key_pem,
        "cert_pem": cert_pem,
        "agent_cert_pem": agent_cert_pem,
    }


# ============================================================
# УТИЛИТЫ (shared/cert_utils)
# ============================================================

def test_extract_cn(pki):
    assert extract_cn(pki["cert_pem"]) == "manager.dcap.local"


def test_generate_ca(pki):
    assert pki["ca_cert_pem"].startswith(b"-----BEGIN CERTIFICATE-----")
    assert pki["ca_key_pem"].startswith(b"-----BEGIN")


def test_cert_issued_by_ca(pki):
    ca_crt = str(pki["base"] / "ca" / "ca.crt")
    result = validate_certificate(pki["cert_pem"], ca_crt)
    assert result["valid"] is True
    assert result["cn"] == "manager.dcap.local"
    assert result["serial"] is not None


def test_validate_with_wrong_ca(pki):
    # Другая CA — сертификат не подпишет
    other_ca_key, other_ca_cert = generate_ca_keypair(cn="Other-CA")
    other_ca_path = pki["base"] / "other_ca.crt"
    other_ca_path.write_bytes(other_ca_cert)
    result = validate_certificate(pki["cert_pem"], str(other_ca_path))
    assert result["valid"] is False
    assert "not signed" in result["error"].lower() or "verify" in result["error"].lower()


# ============================================================
# CertificateManager (manager/src/core/security)
# ============================================================

def test_cert_manager_relaxed_no_certs(tmp_path):
    """mTLS включен, но сертификатов нет → relaxed, is_available=False."""
    from manager.src.core.security import CertificateManager

    cm = CertificateManager(
        {"mtls_enabled": True, "mtls_strict": False, "certs_dir": str(tmp_path / "nope")}
    )
    assert cm.is_available is False
    assert cm.get_server_ssl_context() is None


def test_cert_manager_strict_no_certs(tmp_path):
    """mTLS strict без сертификатов → FileNotFoundError."""
    from manager.src.core.security import CertificateManager

    with pytest.raises(FileNotFoundError):
        CertificateManager(
            {"mtls_enabled": True, "mtls_strict": True, "certs_dir": str(tmp_path / "nope")}
        )


def test_cert_manager_server_ssl_context(pki):
    from manager.src.core.security import CertificateManager

    cm = CertificateManager(
        {"mtls_enabled": True, "mtls_strict": False, "certs_dir": str(pki["base"])}
    )
    assert cm.is_available is True
    ctx = cm.get_server_ssl_context()
    assert ctx is not None
    assert ctx.verify_mode in (ssl.CERT_OPTIONAL, ssl.CERT_REQUIRED)
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


def test_cert_manager_verify_client_cert(pki):
    from manager.src.core.security import CertificateManager

    cm = CertificateManager(
        {"mtls_enabled": True, "mtls_strict": False, "certs_dir": str(pki["base"])}
    )
    is_valid, cn, err = cm.verify_client_cert(pki["cert_pem"])
    assert is_valid is True
    assert cn == "manager.dcap.local"
    assert err is None


def test_cert_manager_verify_revoked_cert(pki):
    """Проверка CRL: отозванный сертификат → not valid."""
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from datetime import datetime, timezone
    from manager.src.core.security import CertificateManager

    crl_dir = pki["base"] / "crl"
    crl_dir.mkdir(parents=True, exist_ok=True)

    ca_key = serialization.load_pem_private_key(
        pki["ca_key_pem"], password=None, backend=default_backend()
    )
    ca_cert = x509.load_pem_x509_certificate(pki["ca_cert_pem"], default_backend())
    agent_cert = x509.load_pem_x509_certificate(pki["agent_cert_pem"], default_backend())

    # Создаём CRL с отозванным agent-s3
    crl = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_cert.subject)
        .last_update(datetime.now(timezone.utc))
        .next_update(datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1))
        .add_revoked_certificate(
            x509.RevokedCertificateBuilder()
            .serial_number(agent_cert.serial_number)
            .revocation_date(datetime.now(timezone.utc))
            .build()
        )
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    (crl_dir / "crl.pem").write_bytes(crl.public_bytes(serialization.Encoding.PEM))

    cm = CertificateManager(
        {"mtls_enabled": True, "mtls_strict": False, "certs_dir": str(pki["base"])}
    )
    # agent-s3 отозван через CRL → is_revoked True, но verify считает валидным без CRL-включения
    assert cm.is_revoked(pki["agent_cert_pem"]) is True
    # manager-сертификат не отозван
    assert cm.is_revoked(pki["cert_pem"]) is False


# ============================================================
# SecretsManager (manager/src/core/secrets)
# ============================================================

def test_secrets_env_priority(tmp_path):
    """При отсутствии /run/secrets — читаем из env."""
    with mock.patch.dict(os.environ, {"SECRET_ONE": "env-value"}):
        sm = SecretsManager({"secrets_dir": str(tmp_path / "secrets")})
        assert sm.get("SECRET_ONE") == "env-value"


def test_secrets_default(tmp_path):
    sm = SecretsManager({"secrets_dir": str(tmp_path / "secrets")})
    assert sm.get("NO_SUCH_SECRET", "fallback") == "fallback"


def test_secrets_docker_priority(tmp_path):
    """Docker Secrets приоритетнее env."""
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    # Docker-имя: lowercase без подчёркиваний
    (secrets_dir / "jwtsecretkey").write_text("docker-value\n", encoding="utf-8")

    with mock.patch.dict(os.environ, {"JWT_SECRET_KEY": "env-value"}):
        sm = SecretsManager({"secrets_dir": str(secrets_dir)})
        assert sm.get("JWT_SECRET_KEY") == "docker-value"


def test_secrets_get_required_missing(tmp_path):
    sm = SecretsManager({"secrets_dir": str(tmp_path / "secrets")})
    with pytest.raises(ValueError):
        sm.get_required("REQUIRED_SECRET")


def test_secrets_cache(tmp_path):
    secrets_dir = tmp_path / "secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "sesskey").write_text("c1", encoding="utf-8")
    sm = SecretsManager({"secrets_dir": str(secrets_dir)})
    sm.get("SESS_KEY")
    # Изменяем файл — кэш не должен перечитаться
    (secrets_dir / "sesskey").write_text("c2", encoding="utf-8")
    assert sm.get("SESS_KEY") == "c1"


def test_load_all(tmp_path):
    with mock.patch.dict(os.environ, {"A": "a", "B": "b"}, clear=False):
        sm = SecretsManager({"secrets_dir": str(tmp_path / "x")})
        result = sm.load_all({"A": None, "B": None, "C": "default-c"})
        assert result == {"A": "a", "B": "b", "C": "default-c"}


def test_singleton(tmp_path):
    with mock.patch.dict(os.environ, {"SINGLETON_KEY": "v"}):
        sm1 = get_secrets_manager()
        sm2 = get_secrets_manager()
        assert sm1 is sm2