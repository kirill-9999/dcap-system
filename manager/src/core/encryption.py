"""Шифрование и маскирование находок.

- AES-256-GCM для зашифрованного хранения.
- HMAC-SHA256 для fingerprint (защита от brute-force).
- Маскирование по категориям.
"""
import os
import re
import hmac
import hashlib
import base64
import logging
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)


# ========== КЛЮЧИ ==========

def _maybe_b64decode(data: bytes) -> bytes:
    """Декодирует base64-ключ (скрипт generate_findings_keys.py) или оставляет raw."""
    stripped = data.strip()
    if len(stripped) == 32:
        return stripped
    try:
        decoded = base64.b64decode(stripped, validate=True)
        if decoded:
            return decoded
    except Exception:
        pass
    return stripped


def _read_secret(name: str, default: Optional[bytes] = None) -> bytes:
    """Читает секрет из Docker Secrets → env → default."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read().strip()

    env_val = os.getenv(name.upper())
    if env_val:
        return env_val.encode()

    if default is not None:
        return default

    raise RuntimeError(
        f"Secret '{name}' not found. "
        f"Set Docker Secret /run/secrets/{name} or env {name.upper()}."
    )


# ========== МАСКИРОВАНИЕ ==========

MASK_RULES = {
    "phone": lambda s: _mask_phone(s),
    "email": lambda s: re.sub(r"(\w{2})\w+@", r"\1***@", s),
    "api_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "aws_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "password": lambda s: "***",
    "token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "passport": lambda s: (s[:2] + "** ******") if len(s) >= 2 else "***",
    "snils": lambda s: "***-***-*** **",
    "inn": lambda s: (s[:2] + "**********") if len(s) >= 2 else "***",
    "credit_card": lambda s: "**** **** **** " + s[-4:] if len(s) >= 4 else "***",
    # Имена НЕ маскируются (по решению)
    "person": lambda s: s,
}


def _mask_phone(s: str) -> str:
    """Маскирует телефон (11 цифр: +7XXXXXXXXXX → +7***XXX-XX-XX)."""
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("7"):
        return "+7***" + digits[4:7] + "-" + digits[7:9] + "-" + digits[9:11]
    if len(digits) >= 10:
        # Возвращаем первые 2 и последние 3, остальное — маска
        return digits[:2] + "***" + digits[-3:]
    return "***"


def mask(value: str, category: str) -> str:
    """Маскирует значение по категории."""
    if not value:
        return value
    fn = MASK_RULES.get(category)
    if fn is None:
        # По умолчанию — полная маска
        return "***"
    try:
        return fn(value)
    except Exception as e:
        logger.warning("Mask failed for category=%s: %s", category, e)
        return "***"


def mask_line(line: str, matches: list) -> str:
    """
    Маскирует строку по списку совпадений.

    matches: [(start, end, category), ...]
    """
    if not matches:
        return line

    # Сортируем по убыванию start (чтобы не сбить индексы)
    sorted_matches = sorted(matches, key=lambda m: m[0], reverse=True)

    result = line
    for start, end, category in sorted_matches:
        original = result[start:end]
        masked = mask(original, category)
        result = result[:start] + masked + result[end:]

    return result


# ========== ШИФРОВАНИЕ ==========

class FindingEncryption:
    """
    AES-256-GCM для находок + HMAC-fingerprint.

    Ключи — Docker Secrets (base64, генерируются scripts/generate_findings_keys.py):
      /run/secrets/findings_encryption_key (32 байта)
      /run/secrets/findings_hmac_key        (32 байта)
      /run/secrets/findings_key_id          (строка, напр. "key-2026-09")
    """

    def __init__(self, key: bytes, hmac_key: bytes, key_id: str):
        if len(key) != 32:
            raise ValueError(f"Encryption key must be 32 bytes, got {len(key)}")
        if len(hmac_key) < 32:
            raise ValueError(f"HMAC key must be >= 32 bytes, got {len(hmac_key)}")

        self.aes = AESGCM(key)
        self.hmac_key = hmac_key
        self.key_id = key_id

    @classmethod
    def from_secrets(cls) -> "FindingEncryption":
        key = _read_secret("findings_encryption_key")
        hmac_key = _read_secret("findings_hmac_key")
        key_id_bytes = _read_secret("findings_key_id", default=b"key-2026-09")
        key_id = key_id_bytes.decode() if isinstance(key_id_bytes, bytes) else key_id_bytes

        # Secrets, сгенерированные scripts/generate_findings_keys.py, — base64.
        # Поддерживаем оба формата (raw 32 байта и base64).
        key = _maybe_b64decode(key)
        hmac_key = _maybe_b64decode(hmac_key)

        return cls(key=key, hmac_key=hmac_key, key_id=key_id)

    @classmethod
    def from_env_or_default(cls) -> "FindingEncryption":
        """
        Fallback для dev: генерирует ключи, если не заданы.
        В production — Docker Secrets обязательны.
        """
        if os.path.exists("/run/secrets/findings_encryption_key"):
            return cls.from_secrets()

        if os.getenv("FINDINGS_ENCRYPTION_KEY"):
            key = base64.b64decode(os.getenv("FINDINGS_ENCRYPTION_KEY"))
            hmac_key = base64.b64decode(os.getenv("FINDINGS_HMAC_KEY"))
            key_id = os.getenv("FINDINGS_KEY_ID", "key-dev")
            return cls(key, hmac_key, key_id)

        # Dev: генерируем ephemeral (предупреждение!)
        logger.warning(
            "Findings keys not configured! Using ephemeral keys. "
            "Data encrypted with them will be LOST on restart. "
            "Set Docker Secrets or FINDINGS_ENCRYPTION_KEY env."
        )
        return cls(
            key=os.urandom(32),
            hmac_key=os.urandom(32),
            key_id="key-ephemeral",
        )

    def encrypt(self, plaintext: str) -> str:
        """Шифрует строку → base64(nonce + ciphertext)."""
        if not plaintext:
            return ""
        nonce = os.urandom(12)
        ct = self.aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Расшифровывает base64(nonce + ciphertext) → строка."""
        if not ciphertext:
            return ""
        try:
            data = base64.b64decode(ciphertext)
            nonce, ct = data[:12], data[12:]
            return self.aes.decrypt(nonce, ct, None).decode("utf-8")
        except Exception as e:
            logger.error("Decryption failed: %s", e)
            raise ValueError("Decryption failed") from e

    def fingerprint(self, file_path: str, line: int, match: str, category: str) -> str:
        """
        HMAC-SHA256 от (file_path, line, match, category).
        Защита от brute-force по fingerprint.
        """
        msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
        return hmac.new(self.hmac_key, msg, hashlib.sha256).hexdigest()


# ========== СИНГЛТОН ==========

_encryption_instance: Optional[FindingEncryption] = None


def get_encryption() -> FindingEncryption:
    """Синглтон для доступа к шифрованию."""
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = FindingEncryption.from_env_or_default()
    return _encryption_instance


def reset_encryption():
    """Сброс синглтона (для тестов)."""
    global _encryption_instance
    _encryption_instance = None