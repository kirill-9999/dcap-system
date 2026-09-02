"""Общие утилиты для работы с сертификатами (shared между компонентами)."""

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger(__name__)


def generate_ca_keypair(
    cn: str = "DCAP-CA",
    valid_days: int = 3650,
    key_size: int = 4096,
) -> tuple:
    """Сгенерировать CA-ключевую пару и самоподписанный сертификат.

    Возвращает (ca_key, ca_cert) в PEM-формате (bytes).
    """
    key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Security"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DCAP"),
        ]
    )
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(
            datetime.now(timezone.utc).replace(
                year=datetime.now(timezone.utc).year + (valid_days // 365)
            )
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
    )
    # SKI (Subject Key Identifier) для CA — иначе некоторые клиенты
    # отклоняют серверный сертификат ошибкой "Missing Authority Key Identifier"
    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False,
    )
    cert = builder.sign(key, hashes.SHA256(), default_backend())
    return (
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        cert.public_bytes(serialization.Encoding.PEM),
    )


def generate_component_keypair(
    cn: str,
    ca_key_pem: bytes,
    ca_cert_pem: bytes,
    san: Optional[str] = None,
    valid_days: int = 365,
    key_size: int = 2048,
) -> tuple:
    """Сгенерировать ключевую пару для компонента и подписать CA.

    Возвращает (cert_pem, key_pem) в PEM-формате (bytes).
    """
    ca_key = serialization.load_pem_private_key(
        ca_key_pem, password=None, backend=default_backend()
    )
    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem, default_backend())

    key = rsa.generate_private_key(
        public_exponent=65537, key_size=key_size, backend=default_backend()
    )

    builder = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
        )
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1))
    )

    if san:
        dns_names = []
        ip_addresses = []
        for val in san.split(","):
            val = val.strip()
            if val.startswith("DNS:"):
                dns_names.append(x509.DNSName(val[4:].strip()))
            elif val.startswith("IP:"):
                ip_str = val[3:].strip()
                try:
                    ip_addresses.append(
                        x509.IPAddress(__import__("ipaddress").ip_address(ip_str))
                    )
                except ValueError:
                    logger.warning("Invalid IP in SAN: %s", ip_str)

        san_ext = x509.SubjectAlternativeName(dns_names + ip_addresses)
        builder = builder.add_extension(san_ext, critical=False)

    # AKID (Authority Key Identifier) = SKI issuer (CA)
    builder = builder.add_extension(
        x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
        critical=False,
    )
    # SKI для компонента
    builder = builder.add_extension(
        x509.SubjectKeyIdentifier.from_public_key(key.public_key()),
        critical=False,
    )

    cert = builder.sign(ca_key, hashes.SHA256(), default_backend())

    return (
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
    )


def extract_cn(cert_pem: bytes) -> Optional[str]:
    """Извлечь Common Name из PEM-сертификата."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            return cn_attrs[0].value
    except Exception as e:
        logger.error("Failed to extract CN: %s", e)
    return None


def extract_serial(cert_pem: bytes) -> Optional[str]:
    """Извлечь серийный номер сертификата (hex)."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        return format(cert.serial_number, "x")
    except Exception as e:
        logger.error("Failed to extract serial: %s", e)
    return None


def validate_certificate(
    cert_pem: bytes,
    ca_cert_path: str,
    crl_path: Optional[Path] = None,
) -> Dict:
    """Проверить сертификат: подпись CA, срок действия, CRL.

    Возвращает {"valid": bool, "error": str|None, "cn": str|None, "serial": str|None}.
    """
    result = {"valid": False, "error": None, "cn": None, "serial": None}

    try:
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        ca_cert = x509.load_pem_x509_certificate(
            Path(ca_cert_path).read_bytes(), default_backend()
        )

        # Проверка подписи CA
        ca_pubkey = ca_cert.public_key()
        try:
            sig_alg = cert.signature_algorithm_oid
            from cryptography.hazmat.primitives.asymmetric import padding as asym_padding

            ca_pubkey.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                asym_padding.PKCS1v15(),
                cert.signature_hash_algorithm,
            )
        except Exception:
            result["error"] = "Certificate not signed by CA"
            return result

        # Проверка срока действия
        now = datetime.now(timezone.utc)
        if now < cert.not_valid_before_utc:
            result["error"] = "Certificate not yet valid"
            return result
        if now > cert.not_valid_after_utc:
            result["error"] = "Certificate expired"
            return result

        # CN
        result["cn"] = extract_cn(cert_pem)
        result["serial"] = format(cert.serial_number, "x")

        # CRL
        if crl_path and crl_path.exists():
            crl_pem = crl_path.read_bytes()
            crl = x509.load_pem_x509_crl(crl_pem, default_backend())
            for revoked in crl:
                if revoked.serial_number == cert.serial_number:
                    result["error"] = "Certificate revoked (CRL)"
                    return result

        result["valid"] = True

    except Exception as e:
        result["error"] = str(e)

    return result


def is_certificate_revoked(cert_pem: bytes, crl_path: str) -> bool:
    """Быстрая проверка CRL (без валидации подписи/срока)."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        crl = x509.load_pem_x509_crl(
            Path(crl_path).read_bytes(), default_backend()
        )
        for revoked in crl:
            if revoked.serial_number == cert.serial_number:
                return True
    except Exception:
        pass
    return False


def fingerprint_hex(cert_pem: bytes, algorithm: str = "sha256") -> Optional[str]:
    """SHA-256 fingerprint сертификата (hex)."""
    try:
        cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
        fp = cert.fingerprint(hashes.SHA256())
        return ":".join(f"{b:02X}" for b in fp)
    except Exception:
        return None
