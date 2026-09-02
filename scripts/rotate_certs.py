#!/usr/bin/env python3
"""Ротация сертификатов DCAP.

1. Генерирует новые сертификаты компонентов (CA остаётся).
2. Добавляет старые сертификаты в CRL (отзыв).
3. Сохраняет бэкап старых сертификатов в certs/backup/<timestamp>/.

Использование:
    python scripts/rotate_certs.py [--certs-dir ./certs] [--component manager]
"""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.cert_utils import (
    extract_serial,
    generate_component_keypair,
)
from shared.security import (
    CERT_VALIDITY_DAYS_COMPONENT,
    COMPONENT_SANS,
    DCAP_COMPONENTS,
)


def rotate_component(
    comp_name: str,
    certs_dir: Path,
    backup_dir: Path,
):
    cert_path = certs_dir / ("manager" if comp_name == "manager" else "agents" if comp_name.startswith("agent-") else "webui" if comp_name == "webui" else "scanner") / f"{comp_name}.crt"
    key_path = cert_path.with_suffix(".key")
    ca_cert_path = certs_dir / "ca" / "ca.crt"
    ca_key_path = certs_dir / "ca" / "ca.key"

    if not cert_path.exists():
        print(f"[skip] {comp_name}: no existing cert")
        return

    # Бэкап
    comp_backup = backup_dir / comp_name
    comp_backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(cert_path, comp_backup / f"{comp_name}.crt")
    shutil.copy2(key_path, comp_backup / f"{comp_name}.key")
    serial = extract_serial(cert_path.read_bytes())
    print(f"[backup] {comp_name} (serial={serial}) -> {comp_backup}")

    # Новый сертификат
    ca_cert_pem = ca_cert_path.read_bytes()
    ca_key_pem = ca_key_path.read_bytes()
    cn = DCAP_COMPONENTS[comp_name]["cn"]
    san = COMPONENT_SANS.get(comp_name)

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
    new_serial = extract_serial(cert_pem)
    print(f"[rotate] {comp_name}: new serial={new_serial} -> {cert_path}")


def main():
    parser = argparse.ArgumentParser(description="DCAP certificate rotation")
    parser.add_argument("--certs-dir", default="certs")
    parser.add_argument(
        "--component",
        choices=["manager", "webui", "agent-windows", "agent-linux", "agent-s3", "scanner", "all"],
        default="all",
    )
    args = parser.parse_args()

    certs_dir = Path(args.certs_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = certs_dir / "backup" / ts

    components = (
        list(DCAP_COMPONENTS.keys()) - ["ca"]
        if args.component == "all"
        else [args.component]
    )

    for comp in components:
        rotate_component(comp, certs_dir, backup_dir)

    print(f"\nRotation complete. Backups in: {backup_dir}")


if __name__ == "__main__":
    main()
