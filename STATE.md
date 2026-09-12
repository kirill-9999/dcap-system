markdown
# 📊 STATE.md — Текущее состояние DCAP

> **Обновляется кодером в конце каждого рабочего дня.**
> Это единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 12.09.2026
**Текущая версия:** v3.10.0
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 День 40.2 — Findings Refactor: сканер (построчно + FP + дедуп) реализован и протестирован (unit 34 + e2e 17/4 skip)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 40.3 — Findings Refactor: WebUI (находки, каталог, FP) |
| Статус дня | 📋 Запланирован |
| Последний принятый отчёт | `day_40.2_report.md` (v3.10.0, Findings Refactor: сканер ✅) |
| Следующий шаг | ТЗ Дня 40.3 → WebUI находок под новую модель |
| Открытые вопросы к архитектору | WebUI v3.8 читает f.value/file_path → частичная деградация до 40.3 |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия | Отчёт |
|------|--------|--------|-------|
| 28 | WebUI редизайн | v3.0.0 | — |
| 29-35 | Стандартизация, аутентификация, S3, AD, безопасность, архивация, Secret Scanner | до v3.4.0 | — |
| 36-37 | Масштабирование (PG, Redis, Celery) | v3.5.0 | — |
| 38 | Контейнеризация и деплой | v3.6.0 | `day_38_report.md` |
| 38.5 | Scanner: Docker → хост | v3.6.2 | `day_38.5_report.md` |
| 39 | Мониторинг + Heartbeat-thread | v3.7.0 | `day_39_report.md` |
| 40-41 | Тестирование (E2E + Chaos + Load) | v3.8.0 | `day_40-41_report.md` |
| **40.1** | **Findings Refactor: модель + шифрование + API (Этап 1)** | **v3.9.0** | **`day_40.1_report.md`** |
| **40.2** | **Findings Refactor: сканер (построчно + FP + дедуп, Этап 2)** | **v3.10.0** | **`day_40.2_report.md`** |
| 42 | Публикация на GitHub | — | 📋 |
| 43 | Релиз v3.0.0 | — | 📋 |

---

## ⚠️ Открытые проблемы

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BACKLOG-039 | Аудит NOT NULL полей в приёмных эндпоинтах | 📋 | 🟡 |
| BACKLOG-043 | Прогресс сканера в WebUI (панель «Сканеры») | 📋 v3.0.0 | 🟡 |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth для Prometheus scrape) | 📋 production | 🟡 |
| BACKLOG-045 | Параметризация портов экспортеров в compose | 📋 | 🟢 |
| NEW-40.1 | WebUI v3.8 находок использует f.value/file_path — на новой модели экраны Findings/Dashboard частично деградируют (category pii → finding_type) | 📋 40.3 | 🟡 |

*(Закрытые в v3.7.0: BACKLOG-021, 037, 038, 041, 042 — см. ROADMAP.md)*
*(Закрытые в v3.8.0 при валидации: alembic 002 на fresh-PG, rate-limit/login-limit через env,
гонка /api/tasks/create, tmpfs postgres_test → named volume)*
*(Закрытые в v3.9.0: доступ к «сырым» знамениям в API — теперь только masked + reveal для Auditor)*
*(Закрытые в v3.10.0: сканер переведён на новые находки (Finding + построчно), FP-фильтр до отправки,
дедупликация в Manager — FP не пересоздаются, повторные находки обновляют last_seen_at;
BACKLOG-053/054/055 — закрыты в коде, статус в ROADMAP обновит Архитектор)*

---

## 🚫 Ключевые решения (краткие)

- **Findings = строка/фрагмент** (не файл): `fragment_type`, `line_number`, `bounding_box`, `byte_*`, `hex_preview` (v3.9.0)
- **Гибридное хранение** — masked + AES-256-GCM encrypted; reveal только Auditor с записью audit_logs (v3.9.0)
- **HMAC-SHA256 fingerprint** для дедупликации/сторожевых FP; ключи — Docker Secrets / env (v3.9.0)
- **Сканер шифрует/маскирует находки на хосте до отправки** (AES-256-GCM + маска по категории); без ключей — legacy-режим (открытый текст → шифрует Manager) (v3.10.0)
- **Дедупликация в Manager** по fingerprint: FP не пересоздаются, повторные находки обновляют `last_seen_at`; batch FP-фильтр `check-fingerprints` до отправки (v3.10.0)
- **Scanner — на хосте, не в Docker** (bind-mount невозможен)
- **Heartbeat-thread** — выделенный daemon-поток (v3.7.0)
- **spaCy-модели `sm`** (не `lg`)
- **spnego убран** из requirements (нет на PyPI)
- **Rust Scanner (v3.1.0, BACKLOG-036)** — IPC (JSON-RPC, `interprocess`), CIFS через `pavao` + `libsmbclient`, NFS через `nfs-rs` (чистый Rust, авто-монтирование через API), Tesseract/Presidio на Python

*(Полный список — в `ARCHITECTURE.md`)*

---

## 📁 Последние использованные файлы

- `prompts/reports/day_40.2_report.md` — принят (v3.10.0, Findings Refactor: сканер: unit 34 + e2e 17/4 skip)
- `prompts/archive/day_40.2_scanner_findings.md` — ТЗ архивировано
- `scanner/src/finding.py` — модель Finding (dataclass, построчно)
- `scanner/src/encryption.py` — AES-256-GCM + HMAC-fingerprint + маскирование на стороне сканера
- `scanner/classifiers/pii_classifier.py`, `credentials_classifier.py`, `code_classifier.py` — `scan_line`
- `scanner/connectors/filesystem.py` — `FilesystemConnector` (построчно + контекст)
- `scanner/src/managed_scanner.py` — FP-фильтр, сериализация, построчный конвейер
- `manager/src/api/scanner.py` — submit_results: новый формат + дедупликация
- `tests/unit/test_scanner_findings.py`, `tests/e2e/test_scanner_findings.py` — тесты дня 40.2
- `docs/deployment.md` — env сканера (FINDINGS_*)