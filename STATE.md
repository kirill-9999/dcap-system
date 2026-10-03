> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 03.10.2026
**Текущая версия:** v3.13.28
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1, 2, 3, 4, 5, 7, 8, **9 (Безопасность)** — ✅ ЗАКРЫТЫ. Фикс-спринт Блок 9 (10 багов) ✅ v3.13.28. Следующий шаг — Блок 6 (Агенты).

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | Фикс-спринт Блок 9 (10 багов безопасности) — Блок 9 закрыт |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `block9_fix_sprint_v31328_report.md` (v3.13.28) |
| Следующий шаг | Блок 6 (Агенты) — 3-5 ч |
| Открытые вопросы к архитектору | 1) 3 новые BACKLOG (094, 096, 093); 2) 13 TEST-NOTE (5.2…5.13, 7.1…7.5); 3) BUG-083, 085 — минорные, в v3.1.0; 4) SQLAlchemy не закреплён в requirements — см. «Открытые проблемы» |

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
| 46 (fix3) | Fix-спринт №2: ENV-ключи Findings | **v3.13.11** | `day_46_fix_sprint_2_report.md` |
| 46 (fix3.5) | Fix-спринт №3: OCR, HTTP-retry, Luhn, dedup | **v3.13.12** | `day_46.5_fix_sprint_3_report.md` |
| 46.6-46.7 (fix4) | Fix-спринт №4: OCR-секция + Presidio ru+en | **v3.13.13** | `day_46.7_fix_sprint_4_report.md` |
| 46.8 (fix5) | Fix-спринт №5: url-over-email, OCR-markup, spaCy noise, credentials | **v3.13.14** | `day_46.8_fix_sprint_5_report.md` |
| 46.9 (fix6) | Fix-спринт №6: url-over-email (line_text), аббревиатуры, uk_nhs | **v3.13.15** | `day_46.9_fix_sprint_6_report.md` |
| 46.10 (fix7) | Fix-спринт №7: url = домен email (BUG-075) | **v3.13.16** | `day_46.10_fix_sprint_7_report.md` |
| 47 (test) | Мастер-сессия: Блок 3 (Scanner deep) — **ЗАКРЫТ** | — | ✅ |
| 47.2 (test) | Мастер-сессия: **Блок 8 (Мониторинг) — ЗАКРЫТ** | v3.13.16 | ✅ |
| 47.3 (bug077) | BUG-077: bounding_box=None для OCR + fallback | **v3.13.17** | `day_47.3_fix_bug077_report.md` |
| 47.4 (bug077 diag) | BUG-077 diag: Manager дефолтил bbox (H3) | **v3.13.18** | `day_47.4_bug077_diag_report.md` |
| 47.5 (BACKLOG-086) | Встроенные OCR-фрагменты в БД | **v3.13.19** | `day_47.5_backlog086_embed_fragments_report.md` |
| 47.6 (BUG-080/081) | Reliability сканера: heartbeat backoff + graceful shutdown | **v3.13.20** | `day_47.6_backlog080_081_scanner_reliability_report.md` |
| 47.7 (BUG-086) | Masking контекстов (_CONTEXT_PATTERNS) | **v3.13.21** | `day_47.7_fix_bug086_mask_context_report.md` |
| 48 (Блок 5, п.2.3) | Фильтры/пагинация/аудит/экспорт WebUI | **v3.13.22** | `day_48_block5_webui_filters_report.md` |
| 48.1 (BUG-094) | «BUG-087» аудит reveal: ложное срабатывание | **v3.13.23** | `day_48.1_bug087_audit_user_report.md` |
| 48.2 (BUG-095) | Аудит аутентификации и управления пользователями | **v3.13.24** | `day_48.2_bug095_auth_audit_report.md` |
| 48.3 (BUG-096/096b/097) | `/false-positives` 500, устаревшие E2E, зависшие задания | **v3.13.25** | `day_48.3_bug096_097_report.md` |
| 49 (BUG-098…101, 101b) | PATCH/bulk/DELETE аудит, reset review, FP-пагинация, FP `file_path` | **v3.13.26** | `day_49_bug098_101_report.md` |
| **50 (BUG-102)** | **Retention + sweep падали на Mapper[Finding] ... 'User' (фикс в 6 модулях)** | **v3.13.27** | `day_50_bug102_celery_mapper_report.md` |
| **Фикс-спринт Блок 9** | **10 багов безопасности: BUG-103/105/106/107/108/110/111/114/115/116 + фикс регресса psycopg** | **v3.13.28** | `block9_fix_sprint_v31328_report.md` |

---

## 🔴 Открытые проблемы

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| BACKLOG-094 | WebUI/Manager не пересобирается автоматически при `up -d` | 📋 v3.0.0 | 🟡 |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | 📋 v3.0.0 | 🟡 |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует с живым сканером | 📋 v3.0.0 | 🟡 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит основной стек | 📋 v3.0.0 | 🟡 |
| BACKLOG-046 | Полный E2E-прогон на CI (seed + изоляция сканера) | 📋 v3.0.0 | 🔴 |
| NEW (v3.13.28) | SQLAlchemy не закреплён в requirements — смена мажорной версии ломает запуск на PG. Пока обойдено `_normalize_url()`, но стоит закрепить версию | 📋 v3.0.0 | 🟡 |
| NEW (v3.13.28) | Manager не маскирует `context_*_masked` сам — доверяет суффиксу. Сканер-компромисс положит сырые секреты в БД (проверено вручную) | 📋 v3.0.0 | 🟡 |
| **NEW (v3.13.28)** | **Потолок параллелизма = 15, а не 30.** `AuthMiddleware.dispatch` держит сессию открытой через весь `call_next` (`middleware.py:232` — `return` внутри `try`, `finally: db.close()` срабатывает после хендлера). Итого 2 соединения на авторизованный запрос: пул `10 + 20 = 30` делится пополам. При 16 потоках — `QueuePool limit ... reached`, 30-секундные таймауты. `tests/load/test_api_load.py::test_get_findings_load` (20 потоков) не может пройти. Фикс: eagerly грузить роли (`selectinload(User.roles)`) и закрывать сессию в middleware — `DetachedInstanceError` из BUG-048b не вернётся | 📋 **v3.1.0** | 🔴 |

### 🟢 Минорные (v3.1.0)

| ID | Проблема | Приоритет |
|----|----------|-----------|
| BUG-060 | BOM ломает маскирование email | 🟢 v3.1.0 |
| BUG-061 | Сканер не восстанавливает HTTP после падения Manager | 🟡 v3.1.0 |
| BUG-076 | Scanner: `current_task` не сбрасывается | 🟢 v3.1.0 |
| BUG-083 | `order_by=severity` — лексикографический | 🟢 v3.1.0 |
| BUG-085 | `/fragment` для text_line → 400 | 🟢 v3.1.0 |
| BACKLOG-076 | Manager: `findings_updated` | 🟡 v3.1.0 |
| BACKLOG-077 | Сканер: heartbeat до инициализации | 🟢 v3.1.0 |
| BACKLOG-085 | OCR bbox (tesseract tsv) | 🟢 v3.1.0 |
| BACKLOG-087 | Дедупликация фрагментов | 🟢 v3.1.0 |
| BACKLOG-088 | Шифрование `fragment_data` | 🟡 v3.1.0 |
| BACKLOG-089 | Cython-оптимизация | 🟡 v3.1.0 |
| BACKLOG-090 | Быстрые regex: `cre`/`re2` | 🟡 v3.1.0 |
| BACKLOG-091 | TruffleHog — верификация credentials | 🟡 v3.1.0+ |
| BACKLOG-092 | Гибрид Cython + Rust | 🟡 v3.1.0+ |
| BACKLOG-093 | Редизайн WebUI (визуал) | 🟢 v3.1.0 |
| BACKLOG-096 | `run_scanner.py` — `start_metrics_server` | 🟢 v3.1.0 |
| TEST-NOTE-5.3 | Export CSV BOM | 🟢 v3.1.0 |
| TEST-NOTE-5.9 | `by_detector` отсутствует в `/stats` | 🟢 v3.1.0 |
| TEST-NOTE-5.13 | Stale-сканеры в БД | 🟢 v3.1.0 |
| TEST-NOTE-7.2 | `retention.state` — в файле воркера | 📋 v3.1.0 |
| TEST-NOTE-7.3 | `findings.ttl_days=180` — без архивации | 📋 v3.1.0 |
| TEST-NOTE-7.5 | Flower не видит worker'ов | 🟢 v3.1.0 |

### 📋 Документация

| ID | Проблема |
|----|----------|
| TEST-NOTE-5.2 | ARCHITECTURE.md: имена полей API |
| TEST-NOTE-5.4 | `catalog_entries` пуста |
| TEST-NOTE-5.6 | `GET /api/findings` без `task_id` смешивает задачи |
| TEST-NOTE-5.7 | `event_type=finding_reveal` vs `metadata.action=finding_revealed` |
| TEST-NOTE-5.8 | Сканер не перезапускается автоматически |
| TEST-NOTE-5.10 | Глобальная статистика включает устаревшие findings |
| TEST-NOTE-7.1 | `findings_archive` — legacy-таблица |
| TEST-NOTE-7.4 | `run` (sync) ≠ `start` (Celery) |

---

## 🎯 Ключевые решения

**Findings Refactor:**
- Findings = строка/фрагмент, гибрид masked + AES-256-GCM.
- HMAC-SHA256 fingerprint.
- Ключи — только ENV (`FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY`).
- Scanner fail-fast без ключей.
- Дедупликация Manager — глобальная по fingerprint.

**Аудит:**
- Reveal: `event_type=finding_reveal`.
- PATCH/bulk: `finding_confirmed`/`finding_false_positive`/`finding_archived`/`finding_reset` + `via=patch|bulk`.
- DELETE: `finding_deleted` (создаётся до `db.delete`).
- Fragment: `fragment_accessed` (RBAC — Auditor+).
- Auth: 9 event_type (BUG-095), `_sanitize` от паролей/токенов, fail-open.
- ⚠️ SQL: `"user"` — **в кавычках** (иначе PostgreSQL → `CURRENT_USER`).

**Scanner:**
- На хосте, не в Docker.
- Heartbeat-thread (30 с), backoff 5→10→30→60→120.
- Graceful shutdown SIGINT/SIGBREAK.
- OCR bbox до v3.1.0 = None; `/fragment` — embedded-first.
- Встроенные фрагменты в БД (BACKLOG-086).
- Masking контекстов: `_CONTEXT_PATTERNS` (21 паттерн).
- Offline-буфер: `SubmitStatus` (OK/RETRY/LOST).

**WebUI:**
- Прокси пробрасывает заголовки (`forwarded_headers`): `X-Total-Count`, `X-Fragment-*`, `Content-Disposition`.
- Бинарные данные — `fetch() + Blob + Bearer`.
- Фильтры: CSV-категории, `detector`, `fragment_type`, `search`, `order_by=id`.
- FastAPI 0.137 gotcha: `BeforeValidator` в `Annotated` теряется при `Query()` в default.
- `_clamp_int` + `OptInt` для числовых query-параметров.

**Retention (v3.13.27):**
- Политики: audit 90+365, findings 180 (без архивации), tasks 30, logs rotate 30/100 МБ.
- Интервал: 24 ч.
- `audit_logs` партиционирована (RANGE по `created_at`, 13 месяцев + default).
- **BUG-102 fix:** Celery-воркер падал на `Mapper[Finding] ... 'User'` — импорт `User` из `auth.models` в 6 модулях.
- `run` — sync в Manager; `start` — Celery.
- `last_run` — в памяти воркера (не в БД).

**Безопасность (v3.13.28):**
- Порядок middleware: `Metrics → RateLimit → Auth → CORS` (Metrics outermost — видит 401).
- Метка `endpoint` в метриках — шаблон маршрута, не сырой путь (нет cardinality по ID).
- mTLS: CRL проверяется на TLS-уровне (`VERIFY_CRL_CHECK_LEAF`) и в `_check_mtls()` (DER).
- Machine-эндпоинты (`/api/scanner*`, `/api/audit/agents/*`, `/api/audit/events`) не публичные, но пропускаются без JWT — только mTLS.
- `postgresql://` нормализуется в `postgresql+psycopg2://` (`_normalize_url`) — иначе SQLAlchemy 2.1 тянет отсутствующий psycopg v3.

**Оптимизация (v3.1.0+):**
- Cython для горячих функций.
- `cre` / `re2` для regex.
- Rust — только CIFS/NFS + параллелизм.
- TruffleHog — верификация credentials.

---

## 📁 Последние использованные файлы

- `manager/src/auth/middleware.py` — BUG-106: machine ≠ public, вызов `_check_mtls()`.
- `manager/src/core/security.py` — BUG-107/108: CRL, `_to_pem`, `_apply_crl`, `_env_bool`.
- `run_manager.py` — BUG-108: `get_server_ssl_context()`, `_resolve_env`.
- `manager/src/metrics.py`, `manager/src/main.py` — BUG-103: порядок middleware, нормализация endpoint.
- `manager/src/api/findings.py` — BUG-110/111/114/115: reveal 409, masked fallback, аудит экспорта, `require_auth`.
- `scripts/reencrypt_findings.py`, `webui/templates/findings.html`, `webui/static/js/findings.js` — BUG-116: dedup + статус `duplicate`.
- `manager/src/db/session.py`, `manager/src/db/migrations/env.py` — `_normalize_url()` (фикс регресса psycopg).
- `tests/unit/test_security_block9_v31328.py` (42), `tests/e2e/test_security_block9_e2e_v31328.py` (5).
- `docker-compose.yml`, `.env`, `.env.example` — VERSION 3.13.28, `./certs` mount.

---

**Актуально на:** 03.10.2026
**Версия:** v3.13.28
**Следующий шаг:** Блок 6 (Агенты)