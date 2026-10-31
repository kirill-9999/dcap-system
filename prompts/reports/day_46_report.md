# День 46 — Fix-спринт №2 (ТЗ №2): ENV-ключи Findings + ротация (v3.13.11)

**Дата:** 20.09.2026
**Версия:** v3.13.10 → v3.13.11
**Ветка:** `fix/env_keys_findings`
**ТЗ:** `prompts/tz/TZ_FIX_SPRINT_2.md` (ТЗ №2 — ENV-ключи Findings)

---

## 📋 Что сделано

### TASK-018 — Docker Secrets → ENV-only (важно)
- `manager/src/core/encryption.py`:
  - `_read_secret()` (чтение `/run/secrets/*`) → `_read_env()` (только ENV)
  - `from_secrets()` → `from_env()`; `_read_env` бросает `RuntimeError`, если ENV не задан
  - убран fallback на Docker Secrets в `from_env_or_default()`
- `scanner/src/encryption.py`:
  - `_read_optional_secret()` → `_read_optional_env()` (только ENV)
  - `from_env()` читает только `FINDINGS_ENCRYPTION_KEY`/`FINDINGS_HMAC_KEY`/`FINDINGS_KEY_ID`
- `docker-compose.yml`: секции `secrets:` (findings) удалены; ключи передаются через
  `manager.environment` из `.env` (`${FINDINGS_ENCRYPTION_KEY}` и др.)
- BREAKING: Docker Secrets для findings больше не поддерживаются — только ENV.

### TASK-016 — `scripts/reencrypt_findings.py` (новый, важно)
CLI-скрипт перешифровки всех findings старым ключом на новый:
- `--old-key-file`, `--old-hmac-file`, `--new-key-file`, `--new-hmac-file`, `--new-key-id`
- `--dry-run` (без записи), `--batch-size 500`, `--filter-key-id`
- батчевая idempotent перешифровка, commit per batch, отчёт `Processed: X / Total: Y`
- расшифровка/перешифровка `match_text_encrypted`/`line_text_encrypted`;
  fingerprint НЕ пересчитывается
- обработка ошибок: decrypt-ошибка → skip + счётчик; encrypt-ошибка → rollback батча
- `scripts/generate_findings_keys.py` — добавлены `--key-id`/`--output`

### TASK-020 — E2E-тест ротации ключей (новый)
`tests/e2e/test_key_rotation.py` (маркер `e2e`, offline):
- ротация `key-test-01` → `key-test-02`, перешифровка 100 findings, reveal после ротации
- 3 теста: полная ротация, reveal после ротации, работа на новом ключе

### Документация
- CHANGELOG.md — v3.13.11 (breaking change: Docker Secrets → ENV)
- ROADMAP.md — TASK-016/018/020 ✅ (fix3), фикспринт закрыт
- STATE.md — v3.13.11, статус «ТЗ №2 ЗАКРЫТ»
- `.env.example` — секция FINDINGS (ENV-only)

---

## 🧪 Тесты

| Компонент | Результат |
|-----------|-----------|
| `tests/unit` (все) | ✅ 128 passed |
| `tests/unit/test_reencrypt.py` + ENV | ✅ 51 passed |
| `tests/e2e/test_key_rotation.py` (offline) | ✅ 3 passed |
| `tests/e2e/test_key_rotation.py` full | ✅ 3 passed |

---

## 🔍 Открытые проблемы
- Реальный прогон ротации на живом стеке с `reencrypt_findings.py` + перезапуск Manager
  (live-ротация) — следующий шаг перед релизом v3.0.0.

## Команда коммита
```git
git add .env.example CHANGELOG.md ROADMAP.md STATE.md docker-compose.yml manager/src/core/encryption.py scanner/src/encryption.py scripts/generate_findings_keys.py scripts/reencrypt_findings.py tests/e2e/test_key_rotation.py tests/unit/test_encryption.py tests/unit/test_reencrypt.py tests/unit/test_scanner_findings.py
git commit -m "fix: ENV-ключи Findings + ротация — TASK-016/018/020 (v3.13.11)"
```
