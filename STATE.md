> **Обновляется кодером в конце каждого рабочего дня.**
> Это единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 12.09.2026
**Текущая версия:** v3.11.0
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 День 40.3 — Findings Refactor: WebUI реализован (v3.11.0)

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 40.4 — Findings Refactor: фрагменты + экспорт (Этап 4) |
| Статус дня | 📋 Запланирован |
| Последний принятый отчёт | `day_40.3_report.md` (v3.11.0) |
| Следующий шаг | Приёмка отчёта Дня 40.3 → ТЗ Дня 40.4 (фрагменты, экспорт) |
| Открытые вопросы к архитектору | — |

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
| 40.1 | Findings Refactor: модель + шифрование + API (Этап 1) | v3.9.0 | `day_40.1_report.md` |
| 40.2 | Findings Refactor: сканер (Этап 2) | v3.10.0 | `day_40.2_report.md` |
| 40.3 | Findings Refactor: WebUI (Этап 3) | v3.11.0 | `day_40.3_report.md` |
| 40.4 | Findings Refactor: фрагменты + экспорт (Этап 4) | — | 📋 |
| 42.1 | Админ-руководство: установка + конфигурация | — | 📋 |
| 42.2 | Админ-руководство: аутентификация + безопасность | — | 📋 |
| 42.3 | Админ-руководство: сканер + агенты | — | 📋 |
| 42.4 | Админ-руководство: мониторинг + retention + troubleshooting + FAQ | — | 📋 |
| 42 | Публикация на GitHub | — | 📋 |
| 43 | Релиз v3.0.0 | — | 📋 |

---

## ⚠️ Открытые проблемы

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BACKLOG-039 | Аудит NOT NULL полей в приёмных эндпоинтах | 📋 | 🟡 |
| BACKLOG-044 | Защита `/metrics` (JWT/basic_auth для Prometheus scrape) | 📋 production | 🟡 |
| BACKLOG-045 | Параметризация портов экспортеров в compose | 📋 | 🟢 |
| **BACKLOG-063** | **Presidio медленный на файлах 100k+ строк** | 📋 v3.1.0 | 🟡 |
| **BACKLOG-064** | **Бенчмарк построчного сканирования (до/после)** | 📋 v3.1.0 | 🟢 |
| **BACKLOG-065** | **Удалить `findings_old` после проверки** | 📋 v3.0.0 | 🟢 |

*(Закрытые в v3.7.0: BACKLOG-021, 037, 038, 041, 042)*
*(Закрытые в v3.8.0 при валидации: alembic 002 на fresh-PG, rate-limit/login-limit через env, гонка /api/tasks/create, tmpfs postgres_test → named volume)*
*(Закрытые в v3.9.0: доступ к «сырым» значениям в API — только masked + reveal для Auditor; BACKLOG-050/051/052)*
*(Закрытые в v3.10.0: сканер переведён на новую модель (Finding + построчно), FP-фильтр до отправки, дедупликация в Manager; BACKLOG-053/054/055)*
*(Закрытые в v3.11.0: WebUI на строчной модели (BACKLOG-056/057), прогресс сканера (BACKLOG-043), MD5 → SHA-256 (BACKLOG-066), деградация WebUI v3.8 устранена (BACKLOG-061))*

---

## 🔴 Критично к релизу (v3.0.0)

| ID | Задача | День | Статус |
|----|--------|------|--------|
| BACKLOG-058 | Фрагменты изображений | 40.4 | 📋 |
| BACKLOG-060 | Экспорт с маскированием | 40.4 | 📋 |
| BACKLOG-028 | Публикация на GitHub | 42 | 📋 |
| — | Админ-руководство (4 под-дня) | 42.1-42.4 | 📋 |
| — | Релиз v3.0.0 | 43 | 📋 |

---

## 🚫 Ключевые решения (краткие)

**Findings Refactor (v3.9.0-v3.10.0):**
- **Findings = строка/фрагмент** (не файл): `fragment_type`, `line_number`, `bounding_box`, `byte_*`, `hex_preview`
- **Гибридное хранение** — masked + AES-256-GCM encrypted; reveal только Auditor с записью `audit_logs`
- **HMAC-SHA256 fingerprint** для дедупликации/сторожевых FP; ключи — Docker Secrets / env
- **Сканер шифрует/маскирует находки на хосте** до отправки; без ключей — legacy-режим (Manager шифрует сам)
- **Дедупликация в Manager** по fingerprint: FP не пересоздаются, повторные находки обновляют `last_seen_at`
- **Batch FP-фильтр** `check-fingerprints` до отправки
- **MD5 → SHA-256** (BACKLOG-066, крипто-фикс) — **закрыт в 40.3**
- **WebUI на строчной модели** (40.3): `/findings` (фильтры, bulk, экспорт), `/findings/{id}` (reveal + FP), `/catalog` (дерево файл→строки), `/false-positives`; общий `webui/static/js/api.js`; панель «Сканеры» с прогрессом из heartbeat

**Общие:**
- **Scanner — на хосте, не в Docker** (bind-mount невозможен)
- **Heartbeat-thread** — выделенный daemon-поток (v3.7.0)
- **spaCy-модели `sm`** (не `lg`)
- **spnego убран** из requirements (нет на PyPI)
- **Rust Scanner (v3.1.0, BACKLOG-036)** — IPC (JSON-RPC, `interprocess`), CIFS через `pavao` + `libsmbclient`, NFS через `nfs-rs` (чистый Rust, авто-монтирование через API), Tesseract/Presidio на Python

*(Полный список — в `ARCHITECTURE.md`)*

---

## 📘 План админ-руководства (Дни 42.1-42.4)

**Принцип:** документация = проверенный факт. Кодер валидирует каждый раздел по реальному коду.

**Структура `docs/admin-guide/`:**
- `README.md` — оглавление + быстрый старт
- `01-architecture.md`
- `02-installation.md`
- `03-configuration.md`
- `04-authentication.md`
- `05-security.md`
- `06-scanner.md`
- `07-agents.md`
- `08-monitoring.md`
- `09-retention.md`
- `10-troubleshooting.md`
- `11-faq.md`

**Разбивка по дням:**
- 42.1 — установка + конфигурация
- 42.2 — аутентификация + безопасность
- 42.3 — сканер + агенты
- 42.4 — мониторинг + retention + troubleshooting + FAQ

---

## 📁 Последние использованные файлы

- `prompts/reports/day_40.3_report.md` — отчёт v3.11.0
- `prompts/tz/day_40.3_webui_findings.md` — выполнено и заархивировано
- `webui/templates/findings.html`, `finding_detail.html`, `catalog.html`, `false_positives.html` — страницы 40.3
- `webui/static/js/findings.js`, `finding_detail.js`, `catalog.js`, `false_positives.js`, `api.js`, `dashboard.js` — логика 40.3
- `webui/static/css/findings.css` — стили 40.3
- `webui/main.py` — роуты `/findings/{id}`, `/false-positives`
- `manager/src/api/webui.py` — `_scanner_dict(s, db)` + `current_task.progress`
- `scanner/src/managed_scanner.py` — `_legacy_fingerprint` SHA-256 (BACKLOG-066)
- `tests/unit/test_fingerprint.py`, `tests/e2e/test_webui_findings.py` — тесты 40.3
- `docs/deployment.md` — раздел WebUI находок
📌 Что изменилось в STATE.md
#	Изменение
1	Статус: «40.3 в работе» (было «40.2 реализован»)
2	Текущий день: 40.3 (было 40.3 — совпадает)
3	Выполненные дни: добавлены строки 40.3 (🔄), 40.4, 42.1-42.4
4	Открытые проблемы: добавлены BACKLOG-063, 064, 065, 066 (MD5→SHA-256, критично)
5	Новый раздел: «🔴 Критично к релизу (v3.0.0)»
6	Ключевые решения: добавлен MD5→SHA-256
7	Новый раздел: «📘 План админ-руководства (42.1-42.4)»
8	Последние файлы: обновлено (40.3 ТЗ передано, промпты картинок)
💾 Что сохранить для следующей беседы
Если лимит близко — сохрани три файла:

Этот STATE.md (обновлённый)

ROADMAP.md (актуальный — с BACKLOG-050…066, Дни 40.1-40.4, 42.1-42.4)

ARCHITECTURE.md (актуальный — с Findings Refactor, шифрованием)

Плюс краткое резюме:

text
Текущий день: 40.3 (WebUI, в работе)
Версия: v3.10.0
Следующий: 40.4 (фрагменты) → 42.1-42.4 (админ-руководство) → 42 (GitHub) → 43 (релиз)

Ключевое:
- Findings Refactor: 40.1 ✅, 40.2 ✅, 40.3 🔄, 40.4 📋
- MD5 → SHA-256 — критично (BACKLOG-066)
- Админ-руководство: 4 под-дня, кодер валидирует по коду
- Картинка архитектуры: готова (DALL-E) + Mermaid для ARCHITECTURE.md
- Rust Scanner (v3.1.0): IPC, CIFS (pavao), NFS (nfs-rs)

Документация: STATE.md, ROADMAP.md, ARCHITECTURE.md, AGENTS.md