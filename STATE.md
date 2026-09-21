> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 21.09.2026
**Текущая версия:** v3.13.13
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Fix-спринт №4 (TASK-029/030, ТЗ №4) ЗАКРЫТ v3.13.13; live-тест обеих частей (Manager+Scanner) → релиз v3.0.0

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 46.7 — Fix-спринт №4 (ТЗ №4: OCR-секция + Presidio ru+en) |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_46.7_fix_sprint_4_report.md` (v3.13.13) |
| Следующий шаг | Live-прогон OCR/кредиток на тестовом стеке → релиз v3.0.0 |
| Открытые вопросы к архитектору | — |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28-40.4 | WebUI, AD, безопасность, Findings Refactor | до v3.12.0 | *(см. предыдущие STATE)* |
| 42.1-42.4 | Админ-руководство | — | ✅ |
| 43-44 | Блок 1 + AD-контейнер | v3.13.3-8 | `day_43_*`, `day_44_*` |
| 45 (тест) | Мастер-сессия Блок 2 (Auth/RBAC) | v3.13.8 | `STATE_TEST_SESSION.md` |
| 45 (fix1) | Fix-спринт №1: Auth/RBAC | **v3.13.9** | `day_45_fix_sprint_report.md` |
| 46 (fix2) | Fix-спринт №2: middleware BUG-048b | **v3.13.10** | — |
| 46 (fix3) | Fix-спринт №2: ENV-ключи Findings + ротация | **v3.13.11** | `day_46_fix_sprint_2_report.md` |
| 46 (fix3.5) | Fix-спринт №3: OCR, HTTP-retry, Luhn, dedup | **v3.13.12** | `day_46.5_fix_sprint_3_report.md` |
| 46.6-46.7 (fix4) | Fix-спринт №4: OCR-секция + Presidio ru+en | **v3.13.13** | `day_46.7_fix_sprint_4_report.md` |

---

## 🔴 Открытые проблемы

### 🟢 Минорные (не блокеры v3.0.0)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| **BUG-060** | BOM ломает маскирование email (`context_before`) | 📋 v3.1.0 | 🟢 |


### 🟡 Средние (перенесены)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BACKLOG-039 | Аудит NOT NULL полей | 📋 | 🟡 |
| BACKLOG-044 | Защита `/metrics` | 📋 production | 🟡 |
| BACKLOG-045 | Параметризация портов | 📋 | 🟢 |
| BACKLOG-063 | Presidio производительность | 📋 v3.1.0 | 🟡 |
| BACKLOG-064 | Бенчмарк сканирования | 📋 v3.1.0 | 🟢 |
| BACKLOG-065 | Удалить `findings_old` | 📋 v3.0.0 | 🟢 |
| BACKLOG-068 | Per-scanner keys | 📋 v3.1.0 | 🟡 |
ID	Проблема	Статус	Приоритет
BUG-061	Сканер не восстанавливает HTTP после падения Manager	📋 v3.1.0	🟡


*(Закрытые в v3.13.9: BUG-037…059 — все 15)*
*(Закрытые в v3.13.10: BUG-048b)*
*(Закрытые в v3.13.11: TASK-016, TASK-018, TASK-020 — ТЗ №2)*
*(Закрытые в v3.13.12: BUG-067, BUG-063 (Luhn), BUG-066, BUG-065, BUG-061 — ТЗ №3)*
*(Закрытые в v3.13.13: TASK-029 (OCR-секция), TASK-030 (Presidio ru+en) — ТЗ №4)*

---

## 🎯 Ключевые решения

**Findings Refactor (v3.9.0-v3.13.11):**
- Findings = строка/фрагмент, гибрид masked + AES-256-GCM
- HMAC-SHA256 fingerprint
- Ключи Findings — только через ENV (Docker Secrets убраны, TASK-018)
- Scanner fail-fast без ключей
- Ротация с downtime (перешифровка `reencrypt_findings.py` + обновление ENV, TASK-016; E2E — TASK-020)
- Единый ключ для v3.0.0, per-scanner — v3.1.0 (BACKLOG-068)

**Аутентификация (Блок 2):**
- `verify_token(token, expected_type)` — access ≠ refresh
- RBAC системно — `Depends(require_role(...))` во все write-эндпоинты
- Middleware извлекает JWT для machine-API (BUG-048b)
- Cookie `Secure` — env `AUTH_COOKIE_SECURE`
- `jti` + `iat` + Redis blacklist

**Общие:**
- Scanner — на хосте, не в Docker
- Heartbeat-thread
- spaCy `sm`

---

## 📁 Последние использованные файлы

- `TZ_FIX_SPRINT_4.md` — ТЗ №4 (закрыто, v3.13.13)
- `scanner/src/managed_scanner.py` — OCR-секция (TASK-029)
- `scanner/classifiers/pii_classifier.py` — двухпроходный Presidio ru+en (TASK-030)
- `docker-compose.yml`, `.env.example` — VERSION 3.13.13
- `scripts/reencrypt_findings.py` — ротация ключей (TASK-016)
- `scripts/generate_findings_keys.py` — генерация ключей (+ `--key-id`/`--output`)
- `tests/e2e/test_key_rotation.py` — E2E ротации (TASK-020, offline)
- `tests/unit/test_reencrypt.py`, `tests/unit/test_encryption.py` — тесты
- `manager/src/core/encryption.py`, `scanner/src/encryption.py` — ENV-only ключи
- `docker-compose.yml`, `.env.example` — без Docker Secrets, ENV-ключи
- `docs/admin-guide/05-security.md` — ENV-ключи + ротация

---

**Актуально на:** 21.09.2026
**Версия:** v3.13.13
**Следующий шаг:** Live-прогон OCR/кредиток → релиз v3.0.0