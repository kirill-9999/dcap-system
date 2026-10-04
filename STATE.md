> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 04.10.2026
**Текущая версия:** v3.13.32
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1, 2, 3, 4, 5, 6, 7, 8, 9 — ✅ ЗАКРЫТЫ. BACKLOG-097 (S3-коннектор) — все 4 части выполнены: Manager (v3.13.29) + ядро сканера (v3.13.30) + `S3LineConnector` (v3.13.31) + E2E на MinIO и форма S3/MinIO в WebUI (v3.13.32). Следующий шаг — 53.4: форма S3-ресурса в WebUI.

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.3 (BACKLOG-097, часть 4: E2E на MinIO + форма S3/MinIO в WebUI) — выполнен |
| Статус дня | ✅ Выполнен |
| Последний принятый отчёт | `day_53_3_report.md` (v3.13.32) |
| Следующий шаг | 53.4: docs по масштабированию S3-сканирования (лимиты, S3-совместимые хранилища) |
| Открытые вопросы к архитектору | 1) BUG-123 (сбор прав Windows) — Блок 6.5; 2) BUG-125 (MANAGER_URL); 3) BUG-130 (backoff); 4) BUG-135 (BOM в JSON); 5) TEST-NOTE-6.11 — `verify=False` при `secure=false` оставлен сознательно (в production нужен `secure=true`); 6) S3-параллелизм (`max_parallel_files` > 1) — кандидат в v3.1.0 |

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
| 50 (BUG-102) | Retention + sweep падали на Mapper[Finding] ... 'User' | **v3.13.27** | `day_50_bug102_celery_mapper_report.md` |
| **51 (Блок 9)** | **Фикс-спринт Блок 9 (Безопасность)** — 10 BUG | **v3.13.28** | `block9_fix_sprint_v31328_report.md` |
| **52 (Блок 6)** | **Блок 6 (Агенты): Windows + Linux + S3 + MinIO** | **v3.13.28** | `block6_agents_full_report.md` |
| **53.1a (BACKLOG-097)** | **Manager: `ScanTask.source_type` + S3/MinIO-ресурсы, миграция 006** | **v3.13.29** | `day_53_1a_report.md` |
| **53.1b (BACKLOG-097)** | **Scanner: фабрика коннекторов, `_text_scanner.py`, boto3, `source_type` в payload** | **v3.13.30** | `day_53_1b_report.md` |
| **53.2 (BACKLOG-097)** | **Scanner: `S3LineConnector` (streaming, ENV-секреты, OCR/документы) + BUG-136 fix** | **v3.13.31** | `day_53_2_report.md` |
| **53.3 (BACKLOG-097)** | **E2E на MinIO (`test_s3_e2e.py`) + форма S3/MinIO в WebUI + `S3_DEFAULT_ENDPOINT`** | **v3.13.32** | `day_53_3_report.md` |

---

## 🔴 Открытые проблемы

### 🔴 Критичные (v3.0.0 / v3.1.0)

| ID | Проблема | Статус | Приоритет |
|----|----------|--------|-----------|
| **BUG-117** | Manager не маскирует контексты сам (defense-in-depth) | 📋 v3.0.0 hotfix | 🔴 |
| **BUG-118** | Auth middleware держит 2 соединения → потолок 15 | 📋 v3.1.0 | 🔴 |
| **BUG-135** | S3-агент: `json.loads` падает на BOM (UTF-8 BOM) | 📋 v3.1.0 | 🟡 |
| **BUG-123** | Windows-агент: сбор прав = 0 (2 бага) | 📋 Блок 6.5 | 🟡 |
| **BUG-130** | Linux-агент: retry без backoff при ошибке отправки прав | 📋 v3.1.0 | 🟡 |
| **BACKLOG-044** | `/metrics` публичный | 📋 v3.0.0 production | 🟡 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | Статус |
|----|----------|--------|
| BUG-121 | README Windows-агента: неверный SACL (`icacls /audit` не существует) | 📋 v3.1.0 |
| BUG-122 | Linux-агент: unit-файл не portable | ✅ **fixed v3.13.28** |
| BUG-124 | `docker-compose.s3.yml` конфликт по `container_name` | 📋 v3.1.0 |
| BUG-125 | Linux-агент: `MANAGER_URL` env игнорируется | 📋 v3.1.0 |
| BUG-126 | S3-агент: `verify_ssl` строковый, не bool | 📋 v3.1.0 |
| BUG-127 | Windows-агент: «Manager недоступен?» при отправке прав | 📋 вместе с BUG-123 |
| BUG-128 | Кириллица в логах (UTF-8 vs PowerShell 5.1) | 📋 док |
| BUG-129 | Windows-агент: шум от собственного чтения Security Log | 📋 v3.1.0 |
| BUG-131 | WSL → Manager: `localhost:8000` терялся при зависании Docker | ✅ **само-исправился после перезагрузки** |
| BUG-132 | S3-агент не переустанавливает соединение после перезагрузки Docker | 🟢 v3.1.0 |
| BUG-134 | `mc.exe` без alias → файл в локальную папку (не баг DCAP) | 🟢 док |
| BUG-136 | ~~FS-коннектор: cp1251 недостижим~~ | ✅ **fixed v3.13.31** (день 53.2: strict-декод utf-8 → cp1251) |
| BACKLOG-094 | WebUI/Manager не пересобирается автоматически при `up -d` | 📋 v3.0.0 |
| BACKLOG-046 | Полный E2E-прогон на CI | 📋 v3.0.0 |
| TEST-NOTE-5.5 | Осиротевшие сканеры после обновления | 📋 v3.0.0 |
| TEST-NOTE-5.11 | E2E `_assign_task` конкурирует с живым сканером | 📋 v3.0.0 |
| TEST-NOTE-5.12 | `--remove-orphans` сносит основной стек | 📋 v3.0.0 |

### 📝 TEST-NOTE (Блок 6)

| ID | Название |
|----|----------|
| TEST-NOTE-6.1 | MinIO через нативные бинарники (registry proxy) |
| TEST-NOTE-6.2 | `sudo` требует пароль в WSL — обход через `pip --user` |
| TEST-NOTE-6.3 | CloudTrail-формат seed-логов не поддерживается конвертером |
| TEST-NOTE-6.4 | Linux-агент использует `watchdog`, не `inotifywait` |
| TEST-NOTE-6.5 | Проверка прав — в PostgreSQL, не в SQLite |
| TEST-NOTE-6.6 | Счётчик S3 `events_sent=16` при 9 валидных (историч.) |
| TEST-NOTE-6.7 | Python 3.13 DeprecationWarning на `datetime.utcnow()` |
| TEST-NOTE-6.8 | Кириллица в логах — PowerShell 5.1 читает ANSI |
| TEST-NOTE-6.9 | Docker Desktop зависает после длительной работы |
| TEST-NOTE-6.10 | Rate-limit 300/60s мешает интенсивному тестированию |

### 📝 TEST-NOTE (Блок 9, ранее)

| ID | Название |
|----|----------|
| TEST-NOTE-9.1 | Rate-limit per-IP, whitelist не параметризован |
| TEST-NOTE-9.2 | Prometheus → Manager plain HTTP |
| TEST-NOTE-9.3 | Prometheus 5/6 при незапущенном сканере |
| TEST-NOTE-9.5 | `check_hostname=False` на клиентском контексте |
| TEST-NOTE-9.7 | `from_env_or_default` без fail-fast |
| TEST-NOTE-9.8 | `SecretsManager` — мёртвый код |
| TEST-NOTE-9.9 | Ротация ключей не реализована (техдолг ТЗ 40.1) |
| TEST-NOTE-9.10 | Артефакты старых E2E в `audit_logs` |
| TEST-NOTE-9.11 | ORM PK ≠ БД PK (`audit_logs`) |
| TEST-NOTE-9.12 | `default={}` (mutable) в модели AuditLog |
| TEST-NOTE-9.13 | `source_host` = IP WebUI, не клиента |
| TEST-NOTE-9.15 | `commit` на каждое событие аудита |
| TEST-NOTE-9.16 | `action` ≠ `event_type` в audit_logs |
| TEST-NOTE-9.17 | `require_viewer` не используется, = `require_auth` |
| TEST-NOTE-9.18 | `user_roles` без PK/CASCADE |

---

## 🎯 Ключевые решения

**Агенты (Блок 6, v3.13.28):**
- **Windows-агент:** служба `DCAPAuditAgent` (Automatic), читает Security Log через `wevtutil`, отправляет события 4663/4656/4660.
- **Linux-агент:** развёрнут в WSL 2 (Ubuntu 22.04), systemd-user (`~/.config/systemd/user/dcap-audit-agent.service`), переживает restart WSL, использует `watchdog` (не `inotifywait`).
- **S3-агент:** работает с MinIO (нативный, `E:\Dev\MinIO`), читает access-логи JSON/CSV, отправляет в Manager.
- **BUG-120 fixed:** S3-агент переключён с AWS на MinIO.
- **BUG-122 fixed:** systemd-unit Linux-агента portable через плейсхолдеры.

**S3-коннектор сканера (BACKLOG-097, v3.13.29):**
- Часть 1 (53.1a, ✅) — Manager: `ScanTask.source_type` (filesystem | s3 | minio) + миграция 006; `POST /api/resources` учится создавать S3/MinIO-ресурсы (`path = s3://bucket[/prefix]`).
- Тип источника **явный** в задании и в payload `GET /api/scanner/tasks/pending` — сканер больше не угадывает коннектор по префиксу пути.
- `minio` трактуется как `s3`; различие только в `endpoint`.
- Уникальность ресурсов — по `(path, type)` (регрессия BUG-059, ранее проверялся только `path`).
- **Секреты S3 в `scan_config` не пишутся** — только ENV на хосте сканера (`S3_ACCESS_KEY` / `S3_SECRET_KEY`), единая политика TASK-018.
- Части 2, 3 и 4 — ✅ фабрика коннекторов, `_text_scanner.py`, boto3, S3-пайплайн находок, E2E на MinIO, WebUI-форма (53.3).

**Безопасность (Блок 9, v3.13.28):**
- mTLS strict → `CERT_REQUIRED` (BUG-108).
- CRL enforce на 2 уровнях: TLS + middleware (BUG-107).
- Volume PKI: `./certs:/app/certs:ro` (BUG-105).
- Machine-endpoints: mTLS до `_is_public` (BUG-106).
- MetricsMiddleware — outermost + нормализация endpoint (BUG-103).
- Reveal при ошибке → 409 + аудит (BUG-110).
- Rotate keys: пересчёт fingerprint + dedup (BUG-116).
- SQLAlchemy pinned `==2.0.54` (регресс).

---

## 📁 Последние использованные файлы

### День 53.1a — BACKLOG-097 (v3.13.29)
- `manager/src/db/migrations/versions/006_add_source_type.py` — NEW, `scan_tasks.source_type` + индекс, идемпотентная.
- `manager/src/db/models.py` — `ScanTask.source_type` (default `filesystem`, index).
- `manager/src/api/resources.py` — S3/MinIO-ресурсы, валидация `s3://`, уникальность `(path, type)`, `source_type` в задаче.
- `manager/src/api/scanner.py` — `source_type` в payload `GET /api/scanner/tasks/pending`.
- `tests/unit/test_s3_resource_v31329.py` — NEW, 19 тестов.

### Блок 6 (v3.13.28)
- `audit-agent-windows/config.json` — обновлён (hostname, paths).
- `audit-agent-windows/logs/audit_agent.log` — UTF-8.
- `audit-agent-linux/service/dcap-audit-agent.service` — плейсхолдеры.
- `audit-agent-linux/service/install.sh` — подстановка.
- `audit-agent-s3/src/collector.py` — ⚠️ BUG-135 (BOM).
- `scripts/minio-seed/access-logs/*` — seed-логи.
- `docker-compose.yml` — env s3_agent.
- `.env` — S3_ENDPOINT=host.docker.internal:9000.

### Блок 9 (v3.13.28)
- `manager/src/auth/middleware.py` — BUG-106, 107.
- `manager/src/core/security.py` — BUG-107, 108.
- `run_manager.py` — BUG-108.
- `manager/src/api/findings.py` — BUG-110, 111, 114, 115.
- `manager/src/metrics.py`, `main.py` — BUG-103.
- `scripts/reencrypt_findings.py` — BUG-116.
- `manager/src/db/session.py`, `db/migrations/env.py` — psycopg fix.
- `docker-compose.yml`, `.env`, `.env.example` — VERSION 3.13.28.

### Тесты
- `tests/unit/test_s3_resource_v31329.py` (19 тестов) — NEW.
- `tests/unit/test_security_block9_v31328.py` (42 теста) — NEW.
- `tests/e2e/test_security_block9_v31328.py` (5 тестов) — NEW.

---

## 📌 Рекомендации архитектору

1. **53.1b — следующий день:** Scanner: фабрика коннекторов, `_text_scanner.py`, `boto3` в `scanner/requirements.txt`, использование `source_type` в `managed_scanner.py`.
2. **Linux-агент — дотестировать** в новой сессии:
   - Метрики `:9102` из WSL и с хоста.
   - Сквозной поток после restart WSL.
   - BUG-130 (backoff).
3. **BUG-135** (BOM в JSON S3-агента) — фикс в v3.1.0.
4. **BUG-123** (сбор прав Windows) — Блок 6.5.
5. **Rate-limit** — увеличить до 10000 для тестов через `.env`.
6. **SQLAlchemy** — закрепить в `requirements.txt` (уже сделано в v3.13.28).

---

**Актуально на:** 03.10.2026
**Версия:** v3.13.29
**Следующий шаг:** 53.1b — Scanner: фабрика коннекторов, `_text_scanner.py`, boto3, `source_type` в `managed_scanner.py`