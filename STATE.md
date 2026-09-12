markdown
# 📊 STATE.md — Текущее состояние DCAP

> **Обновляется кодером в конце каждого рабочего дня.**
> Это единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 12.09.2026
**Текущая версия:** v3.9.0
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟡 День 40.1 — Findings Refactor (модель + шифрование + API) реализован и протестирован (unit 17 + e2e 5 new)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 40.2 — Findings WebUI (обратная связь по ЭП) |
| Статус дня | 📋 Запланирован |
| Последний принятый отчёт | `day_40.1_report.md` (v3.9.0, Findings Refactor ✅) |
| Следующий шаг | ТЗ Дня 40.2 → WebUI находок под новую модель |
| Открытые вопросы к архитектору | WebUI v3.8 читает f.value/file_path → частичная деградация до 40.2 |

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
| NEW-40.1 | WebUI v3.8 находок использует f.value/file_path — на новой модели экраны Findings/Dashboard частично деградируют (category pii → finding_type) | 📋 40.2 | 🟡 |

*(Закрытые в v3.7.0: BACKLOG-021, 037, 038, 041, 042 — см. ROADMAP.md)*
*(Закрытые в v3.8.0 при валидации: alembic 002 на fresh-PG, rate-limit/login-limit через env,
гонка /api/tasks/create, tmpfs postgres_test → named volume)*
*(Закрытые в v3.9.0: доступ к «сырым» знамениям в API — теперь только masked + reveal для Auditor)*

---

## 🚫 Ключевые решения (краткие)

- **Findings = строка/фрагмент** (не файл): `fragment_type`, `line_number`, `bounding_box`, `byte_*`, `hex_preview` (v3.9.0)
- **Гибридное хранение** — masked + AES-256-GCM encrypted; reveal только Auditor с записью audit_logs (v3.9.0)
- **HMAC-SHA256 fingerprint** для дедупликации/сторожевых FP; ключи — Docker Secrets / env (v3.9.0)
- **Scanner — на хосте, не в Docker** (bind-mount невозможен)
- **Heartbeat-thread** — выделенный daemon-поток (v3.7.0)
- **spaCy-модели `sm`** (не `lg`)
- **spnego убран** из requirements (нет на PyPI)
- **Rust Scanner (v3.1.0, BACKLOG-036)** — IPC (JSON-RPC, `interprocess`), CIFS через `pavao` + `libsmbclient`, NFS через `nfs-rs` (чистый Rust, авто-монтирование через API), Tesseract/Presidio на Python

*(Полный список — в `ARCHITECTURE.md`)*

---

## 📁 Последние использованные файлы

- `prompts/reports/day_40.1_report.md` — принят (v3.9.0, Findings Refactor: unit 17 + e2e 5)
- `prompts/archive/day_40.1_findings_model.md` — ТЗ архивировано
- `manager/src/db/migrations/versions/003_findings_refactor.py` — миграция модели Finding
- `manager/src/core/encryption.py` — AES-256-GCM + HMAC-fingerprint + маскирование
- `manager/src/api/findings.py` — новый API (list/stats/FP/reveal/patch/bulk/delete/check-fingerprints)
- `prompts/tz/day_40.2_*.md` — ожидается