> **Обновляется кодером в конце каждого рабочего дня.**
> Единственный источник правды о текущем состоянии проекта.
> План и бэклог — в `ROADMAP.md`. Архитектура — в `ARCHITECTURE.md`.

**Обновлено:** 25.10.2026
**Текущая версия:** v3.14.15
**Целевая версия:** v3.0.0 (релиз)
**Статус:** 🟢 Блоки 1–9 закрыты. BACKLOG-097 (S3-коннектор) закрыт. WebUI-редизайн этапы 1–5 — **REDESIGN COMPLETE (v3.14.1)**. Grafana протестирована + hotfix (v3.14.2). RBAC hotfix (Users/Roles) — v3.14.3. UI hotfix v3.14.4. 53.4g/h/i (Settings/RBAC/Scanners) — v3.14.5–7. **Retention (Блок 18) — ✅ закрыт (v3.14.4).** **53.4l (дедуп + NER off) — ✅ v3.14.10.** **53.4m (multiprocessing) — ✅ v3.14.11.** **53.4n (resume + логи + reconnect) — ✅ v3.14.12.** **53.4o (pool reuse) — ✅ v3.14.13.** **53.4p (final/release/progress) — ✅ v3.14.14.** **BUG-292 (кодировка `finding_detail.js`) — ✅ v3.14.15.** **WebUI (находки) — ✅ проверено** (Reveal, смена статуса, фильтры, аудит). Unit **528 passed**, e2e — стенд `:18000/:18001`. **Следующий шаг — 53.5 (security_scan) → 55 (GitHub) → 56 (BUG-117) → 57 (релиз v3.0.0).**

---

## 📍 Где мы сейчас

| Параметр | Значение |
|----------|----------|
| Текущий день | 53.4p/53.4o (завершены, v3.14.15) |
| Следующий шаг | **53.5 (security_scan)** → 55 → 56 → 57 |
| Открытых BUG | ~12 (🟢 low / v3.1.0) + BUG-293 (UX аудит, v3.0.1) |
| Открытых BACKLOG | ~50 (BACKLOG-156…315 — v3.1.0/бэклог) + BACKLOG-339 (flaky s3) |
| ТЗ собраны | 0 активных в `prompts/tz/` (53.4l–p — архив) |
| Открытые вопросы к архитектору | 1) BUG-248/249 (Grafana, 🟢 low) — в бэклог; 2) BACKLOG-307 (RBAC Grafana) — v3.1.0; 3) BUG-236 вариант B (webhook) — v3.1.0; 4) Security Gateway (MTA + Squid + ICAP + AI) — **v4.0.0**, после Cython/Rust (v3.1.0) |

---

## ✅ Выполненные дни (v3.0.0)

| День | Задача | Версия |
|------|--------|--------|
| 53.4c/d/e | WebUI-редизайн (этапы 3–5) | v3.14.1 |
| 53.4e-grafana + hotfix | Grafana: тесты + hotfix | v3.14.2 |
| 53.4e-rbac-hotfix | Users/Roles (RBAC) | v3.14.3 |
| 53.4f (тест-инфра) | BUG-259/260/261/263, BACKLOG-317, BUG-262 этап A | v3.14.3 |
| 53.4f (UI hotfix) | Dashboard RBAC/403, users responsive | v3.14.4 |
| **Блок 18 (Retention)** | status/policies/stats, dry-run, run, Celery (API + Beat), export | **v3.14.4** |
| 53.4g (UI hotfix) | Settings, RBAC, Responsive (частично) | v3.14.5 |
| 53.4h (Dashboard RBAC) | `checkAuditAccess()` → `Auth.me()` | v3.14.6 |
| 53.4i (Scanners checkbox) | BUG-278 — чекбоксы неактивных | v3.14.7 |
| 53.4j (scanner perf, ч.1) | os.scandir, lru_cache, префильтры | v3.14.8 |
| 53.4k (scanner perf, ч.2) | singleton extractor, lru_cache | v3.14.9 |
| **53.4l (finding-взрыв)** | дедуп + NER off | **v3.14.10** |
| **53.4m (multiprocessing)** | ProcessPoolExecutor | **v3.14.11** |
| **53.4n (resume/логи/reconnect)** | BUG-280/283/284 | **v3.14.12** |
| **53.4o (pool reuse)** | BUG-286 | **v3.14.13** |
| **53.4p (final/release/progress)** | BUG-287/288/289 | **v3.14.14** |
| **BUG-292 (кодировка UI)** | `finding_detail.js` CP1251 → UTF-8 | **v3.14.15** |

---

## 🔴 Открытые проблемы (топ-35)

### 🔴🔴 Критичные (блокеры v3.0.0)

| ID | Проблема | Статус | ТЗ |
|----|----------|--------|-----|
| **BUG-117** | Manager не маскирует контексты сам | 📋 | день 56 (hotfix) |
| **BUG-172** | Нет `permissions` в RBAC | 📋 | архитектура v3.1.0 |
| **BUG-118** | Auth middleware держит 2 соединения | 📋 | v3.1.0 |
| **BUG-135** | S3-агент: BOM | 📋 | v3.1.0 |
| **BACKLOG-044** | `/metrics` публичный | 📋 | production |
| **BACKLOG-307** | Grafana RBAC + DCAP RBAC (Auth Proxy) | 📋 | v3.1.0 |

### 🟡 Важные (не блокеры v3.0.0)

| ID | Проблема | ТЗ |
|----|----------|-----|
| **BUG-293** | `/audit`: дублирование перевода (`finding_reveal — просмотр оригинала`) | **v3.0.1** |
| **BACKLOG-339** | 1 flaky s3 (unit) | v3.0.1 |
| BUG-248 | `Celery tasks (total)` → `No data` | 🟢 v3.1.0 |
| BUG-249 | `PostgreSQL connections` — легенда | 🟢 v3.1.0 |
| BACKLOG-101 | stroke-SVG иконки | v3.1.0 |
| BACKLOG-102 | light-тема | v3.1.0 |
| BACKLOG-103 | S3 fallback на config-секреты | v3.1.0 |
| BACKLOG-315 | Alertmanager webhook → Manager | v3.1.0 |
| BUG-123 | Windows-агент: сбор прав | 52.2 |
| BUG-125/130 | Linux-агент: env / retry | v3.1.0 |
| BUG-221 | Reveal — странные email | v3.1.0 |
| BUG-235 | SIEM-страницы 404 | v3.1.0 |
| BUG-259/260/261/263 | тест-инфра | ✅ v3.14.3 |
| BUG-262 | E2E-эталон без предусловий | 🟡 этап A ✅; этап B — до 55 |
| BACKLOG-317 | `docker-compose.test.yml` — project name | ✅ v3.14.3 (`name: dcap-test`) |
| BACKLOG-046 | E2E-прогон на CI | день 55 |

---

## 🎯 Ключевые решения (v3.14.10–15)

**Закрыто в 53.4l (v3.14.10):**
- **Дедуп** по `(category, match_text)` — finding-взрыв 609 → 0.6/файл.
  `metadata["locations"]` = все вхождения; `line_number`/`context_*` — первого.
- **NER off** — `PERSON/LOCATION/ORGANIZATION/DATE_TIME/NRP` (99.9% находок — FP;
  `person` не маскируется по `ARCHITECTURE.md`). `ner_enabled=false`.
- `Files/min` 24.0 → 65.8; ETA 22 500: 15.6 ч → 5.7 ч.

**Закрыто в 53.4m (v3.14.11):**
- `ProcessPoolExecutor` — ×2.09 на 4 ядрах (63.7 → 132.9 ф/мин).
- Ленивая инициализация spaCy/OCR (память ×1.54, ≤ ×2).
- `temp_dir` на процесс, graceful `Ctrl+C`, auto-fallback на thread.
- ⚠️ Windows (spawn): ~500 МБ/процесс → `max_workers=2` (16 ГБ), 4 (32 ГБ), 8 (128 ГБ).
  Linux (fork): `max_workers = nproc - 1`, память ×1.

**Закрыто в 53.4n (v3.14.12):**
- **Resume** (chunk-aware): `state.save` после каждого чанка; `Ctrl+C` → `executor.shutdown`
  → `state.save` → `release_task` (pending, не failed); `[Resume] ... с чанка N+1/M`.
- **Логи:** консоль DEBUG (всё), файл `logs/scanner.log` INFO (без спама),
  `print` → `logger.debug`.
- **Reconnect:** `[ManagerClient] [OK] Reconnected (was offline Xs)` — консоль + файл.

**Закрыто в 53.4o (v3.14.13):**
- `ProcessPoolExecutor` — **1 раз** на задачу (вне цикла чанков). Warmup 4 процесса (не 40).
  `Files/min` 30–40 → **132.9**; ETA 22 500: 7–9 ч → ~3 ч.

**Закрыто в 53.4p (v3.14.14):**
- `final=True` — только последний чанк (SubmitResults 200, не 400).
- `release` для `completed`/`pending` — no-op (204), не 400.
- `ScanProgress` — монотонный (`_total_scanned`).

**Закрыто в v3.14.15 (BUG-292):**
- `webui/static/js/finding_detail.js` — CP1251 → UTF-8 (без BOM). Подписи/кнопки — RU,
  Console — 0 ошибок.

**Открыто (v3.0.1):**
- **BUG-293** — `/audit`: дублирование перевода (`finding_reveal — просмотр оригинала`).
- **BACKLOG-339** — 1 flaky s3.

---

## 📌 Рекомендации архитектору

1. **Следующий шаг — 53.5 (security_scan).** SAST/SCA/DAST/secrets/containers
   (ТЗ `day_53_5_security_checks.md` + `scripts/security_scan.ps1`).
2. **Затем — 55** (GitHub-пакет) → **56** (BUG-117) → **57** (релиз v3.0.0).
3. **`STATE_TEST_SESSION.md`** — v3.14.15, WebUI (находки) ✅.
4. **`ARCHITECTURE.md`** — v3.14.15 (scanner: multiprocessing, resume, pool reuse;
   PII: NER off, дедуп; WebUI: UTF-8).
5. **v3.1.0** — 13 направлений + Cython/Rust + Security Gateway (v4.0.0).
6. **v4.0.0** — Security Gateway (MTA + Squid + ICAP + AI Gateway) — после v3.1.0.

---

**Актуально на:** 25.10.2026
**Версия:** v3.14.15
**Следующий шаг:** 53.5 (security_scan) → 55 → 56 → 57