"""Генерация ключей для шифрования находок.

Использование:
    python scripts/generate_findings_keys.py

Создаёт:
    secrets/findings_encryption_key   (32 байта, base64)
    secrets/findings_hmac_key         (32 байта, base64)
    secrets/findings_key_id           (key-YYYY-MM)
"""
import os
import base64
from datetime import datetime
from pathlib import Path


def main():
    secrets_dir = Path("secrets")
    secrets_dir.mkdir(exist_ok=True)

    # 32 байта для AES-256
    encryption_key = os.urandom(32)
    hmac_key = os.urandom(32)
    key_id = f"key-{datetime.utcnow().strftime('%Y-%m')}"

    (secrets_dir / "findings_encryption_key").write_bytes(
        base64.b64encode(encryption_key)
    )
    (secrets_dir / "findings_hmac_key").write_bytes(
        base64.b64encode(hmac_key)
    )
    (secrets_dir / "findings_key_id").write_text(key_id)

    print(f"[OK] Keys generated in {secrets_dir}/")
    print(f"   - findings_encryption_key ({len(encryption_key)} bytes)")
    print(f"   - findings_hmac_key ({len(hmac_key)} bytes)")
    print(f"   - findings_key_id = {key_id}")
    print()
    print("[WARN]  НЕ КОММИТИТЬ В GIT! Добавьте secrets/ в .gitignore")


if __name__ == "__main__":
    main()