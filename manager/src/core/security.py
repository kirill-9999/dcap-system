"""CertificateManager: управление сертификатами для mTLS.

Режим: relaxed (по умолчанию) — если сертификаты не найдены, mTLS отключается.
Режим: strict — Manager не стартует без сертификатов.
"""

import logging
import ssl
from pathlib import Path
from typing import Optional, Tuple

from shared.cert_utils import (
    extract_cn,
    is_certificate_revoked,
    validate_certificate,
)

logger = logging.getLogger(__name__)


class CertificateManager:
    """Управление сертификатами для mTLS."""

    def __init__(self, config: dict):
        self.enabled = config.get("mtls_enabled", False)
        self.strict = config.get("mtls_strict", False)
        self.certs_dir = Path(config.get("certs_dir", "certs"))
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
        """SSL-контекст для uvicorn (серверная сторона +要求 клиентского сертификата)."""
        if not self.is_available:
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(
            certfile=str(self.server_cert_path),
            keyfile=str(self.server_key_path),
        )
        ctx.load_verify_locations(cafile=str(self.ca_cert_path))

        if self.crl_path.exists():
            ctx.load_verify_locations(cafile=str(self.crl_path))

        ctx.verify_mode = ssl.CERT_OPTIONAL
        ctx.set_ciphers(
            "ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS"
        )
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2

        logger.info("mTLS server SSL context created")
        return ctx

    def get_client_ssl_context(self) -> Optional[ssl.SSLContext]:
        """SSL-контекст для проверки клиентских сертификатов (agent)."""
        if not self.is_available:
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.load_verify_locations(cafile=str(self.ca_cert_path))

        if self.crl_path.exists():
            ctx.load_verify_locations(cafile=str(self.crl_path))

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
        """Проверить, отозван ли сертификат через CRL."""
        if not self.crl_path.exists():
            return False
        return is_certificate_revoked(cert_pem, str(self.crl_path))
