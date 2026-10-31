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


# BUG-086 (TASK-053, v3.13.21): универсальные regex для каждой категории
# MASK_RULES. Порядок важен — специфичные токены (ghp_, AKIA, xoxb-) раньше
# generic (token/api_key). high_entropy и person НЕ маскируются в контексте
# (high_entropy — сложный расчёт энтропии, отложено до v3.1.0).
_CONTEXT_PATTERNS = [
    # Credentials — специфичные токены (порядок важен: специфичные раньше generic)
    (r"ghp_[a-zA-Z0-9]{20,}",              "github_token"),
    (r"github_pat_[a-zA-Z0-9_]{20,}",      "github_token"),
    (r"xox[baprs]-[a-zA-Z0-9-]{10,}",      "slack_token"),
    (r"AKIA[A-Z0-9]{16}",                  "aws_key"),        # AWS Access Key ID
    (r"sk-[a-zA-Z0-9-]{20,}",              "api_key"),        # OpenAI-style
    (r"sk_live_[a-zA-Z0-9]{20,}",          "api_key"),        # Stripe
    (r"discord[a-zA-Z0-9_-]{20,}",         "discord_token"),  # Discord — упрощённо
    (r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "jwt_token"),
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----", "ssh_key"),
    (r"Basic [A-Za-z0-9+/=]{10,}",         "basic_auth"),
    (r"[a-z][a-z0-9+.\-]*://[^\s\"']+",    "database_url"),   # postgresql://..., mysql://...
    # Generic password/token в форме KEY=VALUE — две capture-группы:
    # (1) префикс (ключ + разделитель), (2) значение. Маскируется ТОЛЬКО значение.
    (r"(?i)((?:password|passwd|pwd)\s*[:=]\s*)(\S+)",  "password"),
    (r"(?i)((?:api[_-]?key|apikey)\s*[:=]\s*)(\S+)",   "api_key"),
    (r"(?i)((?:token|secret|access[_-]?key)\s*[:=]\s*)(\S+)", "token"),
    # PII
    (r"\S+@\S+\.\S+",                       "email"),
    # Phone: RU + международные
    (r"\+?7[\s\-\(\)]*\d{3}[\s\-\(\)]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}", "phone"),  # RU
    (r"\+1[\s\-\.]?\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4}", "phone"),            # US
    (r"\+\d{1,3}[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}", "phone"),            # generic intl
    # Passport / SNILS / INN / CC
    (r"\d{4}\s?\d{6}",                       "passport"),
    (r"\d{3}[\-\s]\d{3}[\-\s]\d{3}[\-\s]\d{2}", "snils"),
    (r"\d{12}",                              "inn"),
    (r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}", "credit_card"),
]


def mask_context(context: str, category: str = None) -> str:
    """Маскирует контекст (строки до/после).

    BUG-086 (TASK-053, v3.13.21): покрывает все категории из MASK_RULES
    (конвейер _CONTEXT_PATTERNS). Порядок паттернов важен — специфичные
    (github_token, aws_key) раньше generic (token/api_key). Параметр
    `category` сохранён для обратной совместимости (managed_scanner.py).
    high_entropy/person в контексте не маскируются (по решению).
    """
    if not context:
        return context
    result = context
    for pattern, cat in _CONTEXT_PATTERNS:
        def _sub(m, c=cat):
            # BUG-086: generic KEY=VALUE (2 capture-группы) маскирует только
            # значение; для одиночных паттернов маскируется весь match.
            if m.lastindex and m.lastindex >= 2:
                return m.group(1) + mask(m.group(2), c)
            return mask(m.group(), c)

        result = re.sub(pattern, _sub, result)
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
