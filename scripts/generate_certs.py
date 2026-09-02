#!/usr/bin/env python3
"""Генерация PKI-инфраструктуры для DCAP (CA + компоненты + CRL).

Cross-platform: работает на Windows/Linux/macOS без внешних зависимостей
(только cryptography). OpenSSL не требуется.

Использование:
    python scripts/generate_certs.py [--certs-dir ./certs] [--force]
"""

import argparse
import sys
from pathlib import Path

# Добавляем корень проекта для импорта shared/
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.cert_utils import (
    extract_cn,
    fingerprint_hex,
    generate_ca_keypair,
    generate_component_keypair,
)
from shared.security import (
    CERT_VALIDITY_DAYS_CA,
    CERT_VALIDITY_DAYS_COMPONENT,
    COMPONENT_SANS,
    DCAP_COMPONENTS,
)


def create_directories(certs_dir: Path):
    for subdir in ["ca", "manager", "webui", "agents", "scanner", "crl"]:
        (certs_dir / subdir).mkdir(parents=True, exist_ok=True)


def generate_certs(certs_dir: Path, force: bool = False):
    ca_dir = certs_dir / "ca"
    manager_dir = certs_dir / "manager"
    webui_dir = certs_dir / "webui"
    agents_dir = certs_dir / "agents"
    scanner_dir = certs_dir / "scanner"
    crl_dir = certs_dir / "crl"

    # === 1. CA ===
    ca_cert_path = ca_dir / "ca.crt"
    ca_key_path = ca_dir / "ca.key"

    if ca_cert_path.exists() and ca_key_path.exists() and not force:
        print("[skip] CA already exists (use --force to regenerate)")
        ca_cert_pem = ca_cert_path.read_bytes()
        ca_key_pem = ca_key_path.read_bytes()
    else:
        print("[gen] CA (self-signed, 4096-bit RSA)...")
        ca_key_pem, ca_cert_pem = generate_ca_keypair(
            cn=DCAP_COMPONENTS["ca"]["cn"],
            valid_days=CERT_VALIDITY_DAYS_CA,
            key_size=4096,
        )
        ca_cert_path.write_bytes(ca_cert_pem)
        ca_key_path.write_bytes(ca_key_pem)
        print(f"    -> {ca_cert_path}")
        print(f"    -> {ca_key_path}")

    # === 2. Компоненты ===
    components = [
        ("manager", manager_dir),
        ("webui", webui_dir),
    ]
    for agent_name in ["agent-windows", "agent-linux", "agent-s3"]:
        components.append((agent_name, agents_dir))
    components.append(("scanner", scanner_dir))

    for comp_name, comp_dir in components:
        cert_path = comp_dir / f"{comp_name}.crt"
        key_path = comp_dir / f"{comp_name}.key"

        if cert_path.exists() and key_path.exists() and not force:
            print(f"[skip] {comp_name} already exists")
            continue

        cn = DCAP_COMPONENTS[comp_name]["cn"]
        san = COMPONENT_SANS.get(comp_name)

        print(f"[gen] {comp_name} (CN={cn})...")
        cert_pem, key_pem = generate_component_keypair(
            cn=cn,
            ca_key_pem=ca_key_pem,
            ca_cert_pem=ca_cert_pem,
            san=san,
            valid_days=CERT_VALIDITY_DAYS_COMPONENT,
            key_size=2048,
        )
        cert_path.write_bytes(cert_pem)
        key_path.write_bytes(key_pem)
        print(f"    -> {cert_path}")
        print(f"    -> {key_path}")

    # === 3. CRL (пустой на старте) ===
    from cryptography import x509
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import hashes, serialization
    from datetime import datetime, timezone

    ca_key = serialization.load_pem_private_key(
        ca_key_pem, password=None, backend=default_backend()
    )
    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem, default_backend())

    crl = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(ca_cert.subject)
        .last_update(datetime.now(timezone.utc))
        .next_update(datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1))
        .sign(ca_key, hashes.SHA256(), default_backend())
    )
    crl_path = crl_dir / "crl.pem"
    crl_path.write_bytes(crl.public_bytes(serialization.Encoding.PEM))
    print(f"[gen] CRL (empty) -> {crl_path}")

    print("\nAll certificates generated successfully.")
    print(f"CA fingerprint: {fingerprint_hex(ca_cert_pem)}")


def main():
    parser = argparse.ArgumentParser(description="DCAP certificate generator")
    parser.add_argument(
        "--certs-dir",
        default="certs",
        help="Directory for certificates (default: ./certs)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate all certificates (existing will be overwritten)",
    )
    args = parser.parse_args()

    certs_dir = Path(args.certs_dir)
    create_directories(certs_dir)
    generate_certs(certs_dir, force=args.force)


if __name__ == "__main__":
    main()
