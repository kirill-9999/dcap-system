# 🔧 ТЗ №2: ENV-ключи Findings + ротация (v3.13.11)

**Дата:** 20.09.2026
**Версия:** v3.13.10 → **v3.13.11**
**Ветка:** `fix/env_keys_findings`
**Приоритет:** 🔴 важно (блокер v3.0.0)
**Источник:** решение архитектора (ENV-only для ключей Findings), `STATE_TEST_SESSION.md`
**Предыдущее ТЗ:** `TZ_FIX_SPRINT.md` (ТЗ №1) — **ЗАКРЫТО в v3.13.9-v3.13.10**
**Оценка:** ~3 часа

---

## 🎯 Контекст

**Принятые решения (20.09.2026):**

1. **Ключи Findings — ТОЛЬКО через ENV** (Docker Secrets — убрать).
2. **Ротация — с downtime** (перешифровка + обновление ENV), **без `*_OLD`**.
3. **Fail-fast для сканера** (BUG-057) — **уже реализован** в v3.13.9 ✅.
4. **Документация** (`05-security.md` + `SECURITY.md` + `security_checklist.md` + `deployment.md` + `06-scanner.md`) — **уже обновлена** ✅.
5. **Единый ключ** для v3.0.0; per-scanner keys — v3.1.0 (BACKLOG-068).

**Зачем это нужно:**
- mTLS защищает канал, но не данные в покое (БД, бэкапы, RAM).
- Ключи на сканере → Manager **никогда** не видит plaintext (кроме reveal).
- Единый механизм для Docker/systemd/Windows-служб — ENV.
- Соответствие 152-ФЗ/GDPR/PCI DSS.

---

## 📋 Задачи

### TASK-016 — `scripts/reencrypt_findings.py`

**Приоритет:** 🔴 важно

**Файл:** `scripts/reencrypt_findings.py` (**создать**)

**Назначение:** CLI-скрипт для перешифровки всех findings старым ключом на новый.

#### CLI

```bash
python scripts/reencrypt_findings.py \
    --old-key-file secrets/findings_encryption_key \
    --old-hmac-file secrets/findings_hmac_key \
    --new-key-file secrets/new/findings_encryption_key \
    --new-hmac-file secrets/new/findings_hmac_key \
    --new-key-id key-2026-12 \
    [--dry-run] \
    [--batch-size 500] \
    [--filter-key-id key-2026-09]
Аргументы
Аргумент	Обязателен	Описание
--old-key-file	✅	Старый encryption-ключ (base64)
--old-hmac-file	✅	Старый HMAC-ключ (base64)
--new-key-file	✅	Новый encryption-ключ (base64)
--new-hmac-file	✅	Новый HMAC-ключ (base64)
--new-key-id	✅	Строковый ID нового ключа
--dry-run	❌	Не пишет в БД, только считает
--batch-size	❌	Размер батча (по умолчанию 500)
--filter-key-id	❌	Обрабатывать только с этим key_id
Логика
Подключение к БД через manager.src.config.get_config().

Загрузка ключей из файлов (--old-*, --new-*).

Query:

sql
SELECT * FROM findings 
WHERE encryption_key_id != :new_key_id 
  [AND encryption_key_id = :filter_key_id]
Итерация батчами (500):

match_text_plain = old_enc.decrypt(match_text_encrypted).

match_text_encrypted_new = new_enc.encrypt(match_text_plain).

То же для line_text_encrypted (если не NULL).

Fingerprint НЕ пересчитывать (смена ключа сломает FP-фильтр).

encryption_key_id = new_key_id.

Commit per batch.

Прогресс: Processed: X / Total: Y.

Обработка ошибок:

decrypt падает → лог + skip + счётчик.

encrypt падает → rollback батча + прерывание.

Итоговый отчёт:

text
Reencryption complete.
  Total findings:     10000
  Already new key:    2000
  Reencrypted:        7900
  Skipped (error):    100
  Batch size:         500
Требования
Транзакционность батчами.

Идемпотентность (повторный запуск — обрабатывает только оставшиеся).

Логирование в stdout.

Тесты (tests/unit/test_reencrypt.py):

test_reencrypt_basic — 10 находок, проверка расшифровки новым ключом.

test_reencrypt_skips_new_key_id — не трогает перешифрованные.

test_reencrypt_dry_run — без записи.

test_reencrypt_error_handling — повреждённый ciphertext → skip.

TASK-017 — Fail-fast сканера (BUG-057) — ✅ УЖЕ СДЕЛАНО
Приоритет: 🔴 важно
Статус: ✅ ЗАКРЫТО в v3.13.9

Что сделано:

scanner/src/encryption.py::from_env(fail_if_missing=True) — по умолчанию.

get_encryption(fail_if_missing=True) — по умолчанию.

При отсутствии ключей → RuntimeError с понятным сообщением.

Legacy-режим только при DCAP_ALLOW_LEGACY_SCANNER=true.

Верифицировано: task 25/26 в логах — keys=enabled.

Действие: закрыть без изменений.

TASK-018 — Убрать Docker Secrets для Findings
Приоритет: 🟡 важно

3 файла:

1. manager/src/core/encryption.py
Убрать _read_secret (чтение /run/secrets/):

python
# УБРАТЬ:
def _read_secret(name: str, default: Optional[bytes] = None) -> bytes:
    """Читает секрет из Docker Secrets → env → default."""
    secret_path = f"/run/secrets/{name}"
    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read().strip()
    env_val = os.getenv(name.upper())
    ...

# ДОБАВИТЬ:
def _read_env(name: str, default: Optional[bytes] = None) -> bytes:
    """Читает секрет из ENV (только)."""
    env_val = os.getenv(name)
    if env_val:
        return env_val.encode()
    if default is not None:
        return default
    raise RuntimeError(
        f"ENV '{name}' not set. See docs/admin-guide/05-security.md."
    )
Переименовать from_secrets() → from_env():

python
@classmethod
def from_env(cls) -> "FindingEncryption":
    key = _read_env("FINDINGS_ENCRYPTION_KEY")
    hmac_key = _read_env("FINDINGS_HMAC_KEY")
    key_id_bytes = _read_env("FINDINGS_KEY_ID", default=b"key-2026-09")
    key_id = key_id_bytes.decode() if isinstance(key_id_bytes, bytes) else key_id_bytes
    key = _maybe_b64decode(key)
    hmac_key = _maybe_b64decode(hmac_key)
    return cls(key=key, hmac_key=hmac_key, key_id=key_id)
Обновить from_env_or_default() — убрать проверку /run/secrets/:

python
@classmethod
def from_env_or_default(cls) -> "FindingEncryption":
    """
    Fallback для dev: генерирует ephemeral ключи, если не заданы.
    В production — ENV обязательны.
    """
    if os.getenv("FINDINGS_ENCRYPTION_KEY"):
        return cls.from_env()

    # Dev: ephemeral (данные теряются при рестарте)
    logger.warning(
        "Findings keys not configured! Using ephemeral keys. "
        "Set FINDINGS_ENCRYPTION_KEY / FINDINGS_HMAC_KEY env."
    )
    return cls(
        key=os.urandom(32),
        hmac_key=os.urandom(32),
        key_id="key-ephemeral",
    )
Обновить get_encryption() — убрать from_secrets().

Обновить docstring — Docker Secrets → ENV.

2. scanner/src/encryption.py
Убрать чтение /run/secrets/ из _read_optional_secret:

python
# УБРАТЬ:
def _read_optional_secret(secret_name: str, env_name: str) -> Optional[bytes]:
    """Читает секрет из Docker Secrets → env."""
    secret_path = f"/run/secrets/{secret_name}"
    if os.path.exists(secret_path):
        with open(secret_path, "rb") as f:
            return f.read().strip()
    env_val = os.getenv(env_name)
    if env_val:
        return env_val.encode()
    return None

# ДОБАВИТЬ:
def _read_optional_env(env_name: str) -> Optional[bytes]:
    """Читает секрет только из ENV."""
    env_val = os.getenv(env_name)
    if env_val:
        return env_val.encode()
    return None
Обновить вызовы в from_env:

_read_optional_secret("findings_encryption_key", "FINDINGS_ENCRYPTION_KEY") → _read_optional_env("FINDINGS_ENCRYPTION_KEY").

Аналогично для HMAC и KEY_ID.

Обновить docstring — env или Docker Secrets → ENV only.

3. docker-compose.yml
Убрать секцию secrets из manager:

yaml
# УБРАТЬ:
manager:
  secrets:
    - findings_encryption_key
    - findings_hmac_key
    - findings_key_id
Добавить ENV в manager.environment:

yaml
manager:
  environment:
    ...
    FINDINGS_ENCRYPTION_KEY: ${FINDINGS_ENCRYPTION_KEY}
    FINDINGS_HMAC_KEY: ${FINDINGS_HMAC_KEY}
    FINDINGS_KEY_ID: ${FINDINGS_KEY_ID:-key-2026-09}
Убрать секцию secrets в конце файла:

yaml
# УБРАТЬ:
secrets:
  findings_encryption_key:
    file: ./secrets/findings_encryption_key
  findings_hmac_key:
    file: ./secrets/findings_hmac_key
  findings_key_id:
    file: ./secrets/findings_key_id
Обновить .env.example:

ini
# Findings keys (обязательны для production)
FINDINGS_ENCRYPTION_KEY=<base64 32 bytes>
FINDINGS_HMAC_KEY=<base64 32 bytes>
FINDINGS_KEY_ID=key-2026-09
Тесты:

Обновить test_encryption.py (если использовал /run/secrets/).

Добавить test_encryption_env_only — работает только через ENV.

⚠️ Breaking change: Docker Secrets перестанут работать. Предупредить в CHANGELOG.

TASK-019 — Обновить документацию — ✅ УЖЕ СДЕЛАНО
Приоритет: 🟡 важно
Статус: ✅ ЗАКРЫТО

Что сделано (в предыдущей сессии):

SECURITY.md §2 — ENV-only.

docs/security_checklist.md — пункты ENV.

docs/deployment.md — «Ключи Findings через ENV».

docs/admin-guide/05-security.md — ENV + обоснование (§3.2 «Зачем ключи на Scanner»).

docs/admin-guide/06-scanner.md — ENV сканера + fail-fast.

Действие: закрыть без изменений.

TASK-020 — E2E-тест ротации ключей
Приоритет: 🟡 важно

Файл: tests/e2e/test_key_rotation.py (создать)

Сценарий:

Setup:

Поднять тестовый стек с key-test-01.

Создать 100 findings.

Проверить: SELECT COUNT(*) FROM findings WHERE encryption_key_id='key-test-01' = 100.

Ротация:

Сгенерировать key-test-02 (generate_findings_keys.py --key-id key-test-02 --output secrets/new/).

reencrypt_findings.py --old-key-file secrets/findings_encryption_key --new-key-file secrets/new/findings_encryption_key --new-key-id key-test-02.

Обновить ENV Manager → перезапустить.

Verify:

SELECT encryption_key_id FROM findings GROUP BY ... → все key-test-02.

POST /api/findings/{id}/reveal (auditor) → расшифровка работает.

GET /api/findings/{id} → маска корректна.

Cleanup.

Тесты:

test_rotation_preserves_data — данные не потеряны.

test_reveal_after_rotation — reveal работает.

test_old_key_not_required_after_rotation — старый ключ больше не нужен.

TASK-021 — Закрыть ТЗ №1 — ✅ УЖЕ СДЕЛАНО
Приоритет: 🟢 nice-to-have
Статус: ✅ ЗАКРЫТО

Что сделано:

ТЗ №1 (Auth/RBAC) — все 15 задач TASK-001…015 закрыты в v3.13.9.

BUG-048b (middleware) закрыт в v3.13.10.

22 runtime-верификации — все ✅.

118 unit-тестов — зелёные.

Действие: закрыть без изменений.

📊 Сводка задач ТЗ №2
ID	Название	Приоритет	Статус	Оценка
TASK-016	scripts/reencrypt_findings.py	🔴	📋 нужно	1-2 ч
TASK-017	Fail-fast сканера	🔴	✅ done	—
TASK-018	Убрать Docker Secrets	🟡	📋 нужно	30 мин
TASK-019	Документация	🟡	✅ done	—
TASK-020	E2E-тест ротации	🟡	📋 нужно	30 мин
TASK-021	Закрыть ТЗ №1	🟢	✅ done	—
Активные: TASK-016, TASK-018, TASK-020.
Закрыты: TASK-017, TASK-019, TASK-021.

Итого: ~2-3 часа.

🚦 Порядок выполнения
TASK-018 (убрать Docker Secrets) — 30 мин, breaking change.

TASK-016 (reencrypt_findings.py) — 1-2 ч, основа ротации.

TASK-020 (E2E-тест) — 30 мин, verify.

CHANGELOG + версия v3.13.11.

Unit-тесты для reencrypt (4 теста).

Verify — ручной прогон.

✅ Критерии приёмки
□ scripts/reencrypt_findings.py — работает (unit + E2E), dry-run, batch, error handling.
□ Manager не читает /run/secrets/ (только ENV).
□ Scanner не читает /run/secrets/ (только ENV).
□ docker-compose.yml — без секции secrets для findings.
□ E2E-тест ротации зелёный.
□ CHANGELOG.md — обновлён (breaking change: Docker Secrets → ENV).
□ STATE_TEST_SESSION.md — пометка «Блок 2 закрыт, fix-спринт №3 запущен».
□ Версия — v3.13.11 везде (.env, .env.example, webui/config.py, docker-compose.yml).
□ /api/health → 3.13.11.
📌 Коммиты (предлагаемые)
text
fix: BUG-057 — scanner fail-fast без ключей (ENV-only) [v3.13.9]
fix: TASK-018 — убрать Docker Secrets для findings (ENV-only) [v3.13.11]
feat: TASK-016 — reencrypt_findings.py для ротации ключей [v3.13.11]
test: TASK-020 — E2E-тест ротации ключей [v3.13.11]
docs: CHANGELOG v3.13.11 — ENV-only ключи Findings
📚 Ссылки
docs/admin-guide/05-security.md — полная процедура ENV-ключей (§3).

SECURITY.md §2 — модель владения ключами.

docs/security_checklist.md — чеклист ENV.

docs/deployment.md — развёртывание с ENV.

docs/admin-guide/06-scanner.md — ENV сканера + fail-fast.

STATE_TEST_SESSION.md — Блок 2 закрыт.

TZ_FIX_SPRINT.md — ТЗ №1 (закрыто).

🎯 Что после ТЗ №2
CHANGELOG — v3.13.11.

STATE.md — обновить.

ROADMAP.md — TASK-016/018/020 закрыты.

STATE_TEST_SESSION.md — пометка.

GitHub (BACKLOG-028/046) — публикация.

Релиз v3.0.0.

Конец ТЗ №2. Приступай к TASK-018 → TASK-016 → TASK-020.