"""Генерация ключей для шифрования находок.

Использование:
    python scripts/generate_findings_keys.py
    python scripts/generate_findings_keys.py --key-id key-2026-12 --output secrets/new

Создаёт:
    <output>/findings_encryption_key   (32 байта, base64)
    <output>/findings_hmac_key         (32 байта, base64)
    <output>/findings_key_id           (key-YYYY-MM или --key-id)
"""
import argparse
import base64
import os
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Generate Findings keys")
    parser.add_argument(
        "--output",
        default="secrets",
        help="директория для ключей (default: secrets)",
    )
    parser.add_argument(
        "--key-id",
        default=None,
        help="явный key_id (default: key-YYYY-MM)",
    )
    args = parser.parse_args()

    secrets_dir = Path(args.output)
    secrets_dir.mkdir(parents=True, exist_ok=True)

    # 32 байта для AES-256
    encryption_key = os.urandom(32)
    hmac_key = os.urandom(32)
    key_id = args.key_id or f"key-{datetime.utcnow().strftime('%Y-%m')}"

    (secrets_dir / "findings_encryption_key").write_bytes(
        base64.b64encode(encryption_key)
    )
    (secrets_dir / "findings_hmac_key").write_bytes(base64.b64encode(hmac_key))
    (secrets_dir / "findings_key_id").write_text(key_id)

    print(f"[OK] Keys generated in {secrets_dir}/")
    print(f"   - findings_encryption_key ({len(encryption_key)} bytes)")
    print(f"   - findings_hmac_key ({len(hmac_key)} bytes)")
    print(f"   - findings_key_id = {key_id}")
    print()
    print("[WARN]  НЕ КОММИТИТЬ В GIT! Добавьте secrets/ в .gitignore")


if __name__ == "__main__":
    main()