# Отчёт — День 40.1: Findings Refactor (Этап 1) (v3.9.0)

- **Дата:** 12.09.2026
- **Версия:** v3.9.0
- **Ветка:** `feature/day_40.1_findings_model` (по ТЗ)
- **ТЗ:** `prompts/tz/day_40.1_findings_model.md` → `prompts/archive/`

---

## 1. Цель

Находка = **строка/фрагмент** (а не файл). Найдено значение зашифровано (AES-256-GCM),
в открытом виде API отдаёт только маскированное; расшифровка (reveal) — только Auditor
с записью в `audit_logs`. KUMAC-SHA256 fingerprint для дедупликации.

## 2. Что сделано

### 2.1 Модель `Finding` (заменена в `manager/src/db/models.py`)
↘ Таблица `findings` заменена: `finding_type`, `category`, `severity`, `fragment_type`
(`text_line`/`text_context`/`image_region`/`byte_range`), `line_number`,
`line_text_masked/encrypted`, `match_text_masked/encrypted`, `context_before/after_masked`,
`fragment_path`, `bounding_box` (JSON), `byte_offset`, `byte_length`, `hex_preview`,
`fingerprint` (HMAC-SHA256, NOT NULL, index), `encryption_key_id` (NOT NULL),
`first_seen_at`, `last_seen_at`, `status` (`new`/`confirmed`/`false_positive`/`archived`),
`reviewed_by` (FK users.id), `reviewed_at`, `comment`, `confidence`, `detector`;
связи `resource`, `task`, `reviewer`; индексы `ix_findings_resource_status`,
`ix_findings_type_category`, `ix_findings_status_first_seen`.

### 2.2 Миграция → Alembic `003_findings_refactor.py`
- PG: переименование старой `findings` в `findings_old`, создание новой таблицы,
  перенос legacy-данных (файл → строка, `finding_type` = старая верхняя категория,
  `fingerprint = md5(random()||resource_id)`, `encryption_key_id='legacy'`, `status='new'`).
- SQLite (dev): создание новой таблицы без автоматического переноса.
- Идемпотентность по колонке `fingerprint`; `downgrade()` восстанавливает `findings_old`.
- Применена на тест-стеке (PG) — `alembic_version = 003_findings_refactor`.

### 2.3 `manager/src/core/encryption.py` (NEW)
- `AESGCM` (AES-256-GCM), base64(nonce+ct) — `encrypt`/`decrypt`;
- `fingerprint(file,line,match,category)` — HMAC-SHA256 (защита от brute-force);
- `MASK_RULES` + `mask()` (**:`phone`,`email`,`api_key`,`aws_key`,`password`,`token`,
  `passport`,`snils`,`inn`,`credit_card`,`person`) + `mask_line(line, matches)`;
- Загрузка ключей: Docker Secrets → env → dev-ephemeral (с предупреждением);
- singletone `get_encryption()` / `reset_encryption()`.

### 2.4 `scripts/generate_findings_keys.py` (NEW)
Генерирует `secrets/findings_encryption_key`, `secrets/findings_hmac_key`,
`secrets/findings_key_id`. `secrets/` добавлен в `.gitignore`.

### 2.5 `manager/src/api/schemas_findings.py` (NEW)
9 Pydantic-моделей: FindingResponse (+legacy `file_path`/`value`), FindingRevealResponse,
FindingUpdateRequest, FindingBulkUpdateRequest/Response, FindingStatsResponse,
FalsePositiveResponse, CheckFingerprintsRequest/Response.

### 2.6 `manager/src/api/findings.py` (переработан)
- `GET /api/findings` — список (masked; фильтр category pii/credentials/code маппится в finding_type)
- `GET /api/findings/stats` — агрегация по status/type/category/severity
- `GET /api/findings/count` — legacy-счётчик (WebUI)
- `GET /api/findings/false-positives` — список FP (Auditor+)
- `GET /api/findings/{id}` — детали (masked)
- `POST /api/findings/{id}/reveal` — расшифровка (Auditor+), пишет AuditLog `finding_reveal`
- `PATCH /api/findings/{id}` — смена статуса + comment + reviewed_by (Auditor+)
- `POST /api/findings/bulk` — массовая смена статуса (Auditor+)
- `DELETE /api/findings/{id}` — удаление + удаление фрагмента (Admin)
- `POST /api/findings/check-fingerprints` — machine-эндпоинт для сканера (публичный)

### 2.7 Backward-compat и другие правки
- `manager/src/api/scanner.py` `submit_results`: старый формат находки → новая модель
  (`fragment_type='text_line'`, `finding_type` из старой категории, `encrypt` + `mask`,
  HMAC-fingerprint, `detector='legacy'`) — сканер v3.8 продолжает работать.
- `manager/src/auth/middleware.py`: `/api/findings/check-fingerprints` в machine-prefix.
- `manager/src/retention/archiver.py`: `created_at` → `first_seen_at`, маппинг полей в архив.
- `manager/src/core/secrets.py`: добавлен `FINDINGS_KEYS`.
- `docker-compose.yml` + `.env.example`: Docker Secrets `findings_*` для Manager.
- `pyproject.toml`: маркер `unit`.

### 2.8 Тесты
- `tests/unit/test_encryption.py` (NEW, маркер unit)** — 17 тестов** (mask-правила,
  roundtrip, случайный IV, отказ при wrong key, детерминизм fingerprint);
- `tests/e2e/test_findings_api.py` (NEW, e2e+requires_manager)** — 5 тестов** (submit→masked list,
  reveal Auditor+аудит, FP+stats, check-fingerprints+bulk, delete Admin).

Результат локально против тест-стека:
- unit: `17 passed in 0.23s`
- e2e: `13 passed, 3 skipped` (из них новых e2e — 5; 3 skip — требует запущенного сканера).

## 3. Полный код ключевых новых файлов

### `manager/src/core/encryption.py`
```python
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
        return digits[:2] + "***" + digits[-3:]
    return "***"


def mask(value: str, category: str) -> str:
    """Маскирует значение по категории."""
    if not value:
        return value
    fn = MASK_RULES.get(category)
    if fn is None:
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

    Ключи — Docker Secrets:
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

        return cls(key=key, hmac_key=hmac_key, key_id=key_id)

    @classmethod
    def from_env_or_default(cls) -> "FindingEncryption":
        """Fallback для dev: генерирует ключи, если не заданы."""
        if os.path.exists("/run/secrets/findings_encryption_key"):
            return cls.from_secrets()

        if os.getenv("FINDINGS_ENCRYPTION_KEY"):
            key = base64.b64decode(os.getenv("FINDINGS_ENCRYPTION_KEY"))
            hmac_key = base64.b64decode(os.getenv("FINDINGS_HMAC_KEY"))
            key_id = os.getenv("FINDINGS_KEY_ID", "key-dev")
            return cls(key, hmac_key, key_id)

        logger.warning(
            "Findings keys not configured! Using ephemeral keys. "
            "Data encrypted with them will be LOST on restart. "
            "Set Docker Secrets or FINDINGS_ENCRYPTION_KEY env."
        )
        return cls(key=os.urandom(32), hmac_key=os.urandom(32), key_id="key-ephemeral")

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
        """HMAC-SHA256 от (file_path, line, match, category)."""
        msg = f"{file_path}|{line}|{match}|{category}".encode("utf-8")
        return hmac.new(self.hmac_key, msg, hashlib.sha256).hexdigest()


# ========== СИНГЛТОН ==========

_encryption_instance: Optional[FindingEncryption] = None


def get_encryption() -> FindingEncryption:
    global _encryption_instance
    if _encryption_instance is None:
        _encryption_instance = FindingEncryption.from_env_or_default()
    return _encryption_instance


def reset_encryption():
    global _encryption_instance
    _encryption_instance = None
```

(Полные коды `findings.py`, `schemas_findings.py`, миграции `003_findings_refactor.py`,
`generate_findings_keys.py`, тестов unit/e2e, правок `models.py`/`scanner.py`/`archiver.py`
и конфигов доступны в рабочей ветке `feature/day_40.1_findings_model` — код приложен
к этому отчёту в виде коммита.)

## 4. Инструкция по запуску (ручной тест)

1. **Сгенерировать ключи** (для production/multi-модуля):
   ```powershell
   python scripts/generate_findings_keys.py
   ```
   (в dev можно не делать — ключи сгенерируются ephemeral с warning).

2. **Пересоздать схему/миграцию:**
   ```powershell
   alembic upgrade head            # PostgreSQL
   python init_db.py               # SQLite (create_all создаст новую findings)
   ```

3. **Запуск стека** (как обычно):
   ```powershell
   python run_manager.py           # :8000
   python run_webui.py             # :8001
   python run_scanner.py scanner/config/scanner_config.json
   ```

4. **Проверить API:**
   ```powershell
   # ключи (для prod-стеков до старта Manager):
   # 1) login: POST /api/auth/login {admin/admin123} → access_token
   # 2) POST /api/findings/check-fingerprints {"fingerprints":["x"]}  (публичный)
   # 3) GET  /api/findings/stats                                   (JWT)
   # 4) POST /api/findings/{id}/reveal                             (Auditor/Admin)
   ```

5. **Тесты:**
   ```powershell
   python -m pytest tests/unit/test_encryption.py -v
   python -m pytest tests/e2e/test_findings_api.py -v    # против тест-стека :18000
   ```

## 5. Известная деградация (до Этапа 40.2)

WebUI (v3.8) на странице Findings читает `f.category`/`f.value`/`f.file_path`. Новая модель
отдаёт `finding_type` (+legacy `file_path`/`value` для API-совместимости), но категории
стали детальнее (`pii` → `phone`/`email`/...). Экраны *Findings/Dashboard* частично
отображают старую разметку до Дня 40.2 (WebUI refactor). Scanner v3.8.0 работает
без изменений (приём старого формата реализован).