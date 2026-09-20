#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Шифрование и маскирование находок (на стороне сканера).

Дублирует логику Manager — сканер шифрует перед отправкой,
чтобы открытый текст не покидал хост сканирования.
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

# ========== МАСКИРОВАНИЕ ==========

def _mask_email(s: str) -> str:
    """Маскирует email целиком (BUG-044): local и domain.

    us***@ex***.com — первые 2 символа local-part и первого label домена,
    остальное — маска; TLD остаётся видимым.
    """

    def repl(m):
        local = m.group(1)
        domain = m.group(2)
        tld = m.group(3)
        local_out = (local[:2] + "***") if len(local) >= 2 else "***"
        domain_out = (domain[:2] + "***") if len(domain) >= 2 else "***"
        return f"{local_out}@{domain_out}.{tld}"

    return re.sub(r"([\w.+-]+)@([\w.-]+)\.([A-Za-z]{2,})", repl, s)


def _mask_phone(s: str) -> str:
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("7"):
        return "+7***" + digits[4:7] + "-" + digits[7:9] + "-" + digits[9:11]
    if len(digits) >= 10:
        return digits[:2] + "***" + digits[-3:]
    return "***"


MASK_RULES = {
    "phone": lambda s: _mask_phone(s),
    "email": _mask_email,
    "api_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "aws_key": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "password": lambda s: "***",
    "token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "passport": lambda s: (s[:2] + "** ******") if len(s) >= 2 else "***",
    "snils": lambda s: "***-***-*** **",
    "inn": lambda s: (s[:2] + "**********") if len(s) >= 2 else "***",
    "credit_card": lambda s: "**** **** **** " + s[-4:] if len(s) >= 4 else "***",
    # День 40.2: категории credential-паттернов
    "jwt_token": lambda s: (s[:10] + "***") if len(s) > 10 else "***",
    "ssh_key": lambda s: "***ssh-private-key***",
    "github_token": lambda s: (s[:4] + "***") if len(s) > 4 else "***",
    "slack_token": lambda s: (s[:5] + "***") if len(s) > 5 else "***",
    "discord_token": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    "database_url": lambda s: re.sub(r"//[^@/]+@", "//***@", s) if "@" in s else "***",
    "basic_auth": lambda s: "Basic ***",
    "high_entropy": lambda s: (s[:6] + "***") if len(s) > 6 else "***",
    # Имена НЕ маскируются (по решению)
    "person": lambda s: s,
}


def mask(value: str, category: str) -> str:
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
    """matches: [(start, end, category), ...]"""
    if not matches:
        return line
    # BUG-022.9: при одинаковых (start, end) — оставляем одну (первую в sorted)
    seen_positions = set()
    unique_matches = []
    for m in matches:
        key = (m[0], m[1])
        if key not in seen_positions:
            seen_positions.add(key)
            unique_matches.append(m)
    sorted_matches = sorted(unique_matches, key=lambda m: m[0], reverse=True)
    result = line
    for start, end, category in sorted_matches:
        original = result[start:end]
        masked = mask(original, category)
        result = result[:start] + masked + result[end:]
    return result


def mask_context(context: str, category: str = None) -> str:
    """
    Маскирует контекст (строки до/после).
    Простая эвристика: маскирует всё, что похоже на секрет.

    BUG-022.2: расширена набором PII-паттернов (паспорт/СНИЛС/ИНН/карты),
    помимо телефонов и email. Передача positions находок соседних строк
    (точный пересчёт смещений) — отдельная задача, отложена.
    """
    if not context:
        return context
    result = context
    # Телефоны
    result = re.sub(r"\+?7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}",
                    lambda m: mask(m.group(), "phone"), result)
    # Email
    result = re.sub(r"\S+@\S+\.\S+", lambda m: mask(m.group(), "email"), result)
    # BUG-022.2: паспорт, СНИЛС, ИНН, кредитные карты — тоже PII
    result = re.sub(r"\d{4}\s?\d{6}", lambda m: mask(m.group(), "passport"), result)
    result = re.sub(r"\d{3}[\-\s]\d{3}[\-\s]\d{3}[\-\s]\d{2}", lambda m: mask(m.group(), "snils"), result)
    result = re.sub(r"\d{12}", lambda m: mask(m.group(), "inn"), result)
    result = re.sub(r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}", lambda m: mask(m.group(), "credit_card"), result)
    return result


# ========== ШИФРОВАНИЕ ==========

class ScannerEncryption:
    """
    AES-256-GCM + HMAC-fingerprint (на стороне сканера).

    Ключи — только env:
      FINDINGS_ENCRYPTION_KEY (base64, 32 байта)
      FINDINGS_HMAC_KEY       (base64, 32 байта)
      FINDINGS_KEY_ID         (строка)
    """

    def __init__(self, key: bytes, hmac_key: bytes, key_id: str):
        if len(key) != 32:
            raise ValueError(f"Encryption key must be 32 bytes, got {len(key)}")
        if len(hmac_key) < 32:
            raise ValueError(f"HMAC key must be >= 32 bytes")

        self.aes = AESGCM(key)
        self.hmac_key = hmac_key
        self.key_id = key_id

    @classmethod
    def from_env(cls, fail_if_missing: bool = True) -> Optional["ScannerEncryption"]:
        """
        Загружает ключи из env (только).

        По умолчанию fail_if_missing=True (BUG-057): если ключи не заданы —
        RuntimeError (сканер не стартует). Режим legacy (без шифрования)
        открывается только при DCAP_ALLOW_LEGACY_SCANNER=true.
        """
        enc_key = _read_optional_env("FINDINGS_ENCRYPTION_KEY")
        hmac_key = _read_optional_env("FINDINGS_HMAC_KEY")

        if not enc_key or not hmac_key:
            allow_legacy = os.getenv("DCAP_ALLOW_LEGACY_SCANNER", "false").lower() == "true"
            msg = (
                "FINDINGS_ENCRYPTION_KEY/FINDINGS_HMAC_KEY not set. "
                "Scanner cannot start without encryption keys. "
                "Set them via env. "
                "See docs/admin-guide/05-security.md."
            )
            if fail_if_missing and not allow_legacy:
                raise RuntimeError(msg)
            logger.warning(
                "⚠️ SCANNER IN LEGACY MODE — plaintext leaves host! DEV ONLY! "
                "Set DCAP_ALLOW_LEGACY_SCANNER=false in prod."
            )
            return None

        try:
            key = base64.b64decode(enc_key)
            hm = base64.b64decode(hmac_key)
            key_id = _read_optional_env("FINDINGS_KEY_ID")
            if isinstance(key_id, bytes):
                key_id = key_id.decode()
            if not key_id:
                key_id = "key-2026-09"
            return cls(key, hm, key_id)
        except Exception as e:
            logger.error("Failed to load encryption keys: %s", e)
            return None

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        nonce = os.urandom(12)
        ct = self.aes.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    def fingerprint(self, file_path: str, line: int, match: str, category: str) -> str:
        msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
        return hmac.new(self.hmac_key, msg, hashlib.sha256).hexdigest()


def _read_optional_env(env_name: str) -> Optional[bytes]:
    """Читает секрет только из ENV. Не падает, если не задан."""
    env_val = os.getenv(env_name)
    if env_val:
        return env_val.encode()
    return None


# ========== СИНГЛТОН ==========

_instance: Optional[ScannerEncryption] = None
_initialized = False


def get_encryption(fail_if_missing: bool = True) -> Optional[ScannerEncryption]:
    """Синглтон. По умолчанию fail-fast (BUG-057): без ключей — RuntimeError.

    Возвращает None только при явном fail_if_missing=False или
    DCAP_ALLOW_LEGACY_SCANNER=true.
    """
    global _instance, _initialized
    if not _initialized:
        _instance = ScannerEncryption.from_env(fail_if_missing=fail_if_missing)
        _initialized = True
    return _instance


def reset_encryption():
    global _instance, _initialized
    _instance = None
    _initialized = False


__all__ = [
    "ScannerEncryption",
    "get_encryption",
    "reset_encryption",
    "mask",
    "mask_line",
    "mask_context",
    "MASK_RULES",
]
