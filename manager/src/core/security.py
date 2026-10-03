"""CertificateManager: управление сертификатами для mTLS.

Режим: relaxed (по умолчанию) — если сертификаты не найдены, mTLS отключается.
Режим: strict — Manager не стартует без сертификатов.
"""

import logging
import os
import ssl
from pathlib import Path
from typing import Optional, Tuple

from shared.cert_utils import (
    extract_cn,
    is_certificate_revoked,
    validate_certificate,
)

logger = logging.getLogger(__name__)


def _to_pem(cert: bytes) -> bytes:
    """DER → PEM. Уже-PEM возвращается как есть (ssl.DER_cert_to_PEM_cert
    требует именно DER и на PEM падает)."""
    if not cert:
        return cert
    if b"-----BEGIN" in cert[:64]:
        return cert
    try:
        return ssl.DER_cert_to_PEM_cert(cert).encode("ascii")
    except Exception as e:
        logger.warning("DER→PEM conversion failed: %s", e)
        return cert


def _env_bool(name: str, default: bool) -> bool:
    """Читает булеву ENV-переменную (1/true/yes/on)."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class CertificateManager:
    """Управление сертификатами для mTLS."""

    def __init__(self, config: dict):
        # BUG-108 (v3.13.28): приоритет ENV над config.json. docker-compose
        # прокидывает MTLS_ENABLED/MTLS_STRICT/CERTS_DIR, и config.json может
        # не содержать соответствующих ${VAR:-default} подстановок — раньше в
        # этом случае ENV молча игнорировался, и main.py/run_manager.py
        # расходились во мнении, включён ли mTLS.
        self.enabled = _env_bool("MTLS_ENABLED", bool(config.get("mtls_enabled", False)))
        self.strict = _env_bool("MTLS_STRICT", bool(config.get("mtls_strict", False)))
        certs_dir = os.getenv("CERTS_DIR") or config.get("certs_dir", "certs")
        self.certs_dir = Path(certs_dir)
        self.ca_cert_path = self.certs_dir / "ca" / "ca.crt"
        self.server_cert_path = self.certs_dir / "manager" / "manager.crt"
        self.server_key_path = self.certs_dir / "manager" / "manager.key"
        self.crl_path = self.certs_dir / "crl" / "crl.pem"

        self._files_ok = False
        if self.enabled:
            self._files_ok = self._validate_files()

    def _validate_files(self) -> bool:
        required = [self.ca_cert_path, self.server_cert_path, self.server_key_path]
        missing = [p for p in required if not p.exists()]
        if missing:
            msg = "mTLS enabled but certificate files missing: %s" % ", ".join(
                str(p) for p in missing
            )
            if self.strict:
                raise FileNotFoundError(msg)
            logger.warning("%s — mTLS disabled", msg)
            return False
        return True

    @property
    def is_available(self) -> bool:
        return self.enabled and self._files_ok

    def get_server_ssl_context(self) -> Optional[ssl.SSLContext]:
        """SSL-контекст для uvicorn (серверная сторона + требование клиентского сертификата).

        BUG-107 (v3.13.28): включена проверка CRL (VERIFY_CRL_CHECK_LEAF).
        Раньше CRL только подгружался, но никогда не проверялся.
        BUG-108 (v3.13.28): verify_mode зависит от режима — в strict клиентский
        сертификат обязателен (CERT_REQUIRED), в relaxed — опционален.
        """
        if not self.is_available:
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(
            certfile=str(self.server_cert_path),
            keyfile=str(self.server_key_path),
        )
        ctx.load_verify_locations(cafile=str(self.ca_cert_path))

        self._apply_crl(ctx)

        # BUG-108: strict требует клиентский сертификат на уровне TLS.
        ctx.verify_mode = ssl.CERT_REQUIRED if self.strict else ssl.CERT_OPTIONAL
        ctx.set_ciphers(
            "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
        )
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        logger.info(
            "mTLS server SSL context created (mode=%s, crl=%s)",
            "strict" if self.strict else "relaxed",
            "on" if self.crl_path.exists() else "off",
        )
        return ctx

    def _apply_crl(self, ctx: ssl.SSLContext) -> bool:
        """BUG-107: подключает CRL и включает её проверку.

        Возвращает True, если CRL подключена. Отсутствие CRL — не ошибка
        (relaxed-режим dev без выпуска CRL).
        """
        if not self.crl_path.exists():
            return False
        try:
            ctx.load_verify_locations(cafile=str(self.crl_path))
            ctx.verify_flags |= ssl.VERIFY_CRL_CHECK_LEAF
        except Exception as e:
            logger.warning("Failed to enable CRL verification: %s", e)
            return False
        return True

    def get_client_ssl_context(self) -> Optional[ssl.SSLContext]:
        """SSL-контекст для проверки клиентских сертификатов (agent)."""
        if not self.is_available:
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(cafile=str(self.ca_cert_path))

        self._apply_crl(ctx)

        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED

        logger.info("mTLS client verification context created")
        return ctx

    def verify_client_cert(
        self, cert_pem: bytes
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Проверить клиентский сертификат.

        Возвращает (is_valid, cn, error_message).
        """
        if not self.is_available:
            return False, None, "mTLS not available"

        try:
            result = validate_certificate(cert_pem, str(self.ca_cert_path), self.crl_path)
            if not result["valid"]:
                return False, None, result.get("error", "validation failed")

            cn = extract_cn(cert_pem)
            return True, cn, None

        except Exception as e:
            logger.error("Certificate verification failed: %s", e)
            return False, None, str(e)

    def is_revoked(self, cert_pem: bytes) -> bool:
        """Проверить, отозван ли сертификат через CRL.

        Принимает PEM или DER (как отдаёт `SSLSocket.getpeercert(binary_form=True)`).
        Некорректные данные считаются «не отозван» (fail-open на стороне
        парсинга — сам CRL уже проверен TLS-стеком через VERIFY_CRL_CHECK_LEAF).
        """
        if not self.crl_path.exists():
            return False
        return is_certificate_revoked(_to_pem(cert_pem), str(self.crl_path))
