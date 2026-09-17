# 🧪 DCAP Test Session — Состояние на 16.09.2026

> **Мастер-сессия ручного тестирования DCAP v3.13.2**
> Блок 1 (Запуск + Smoke + Findings + WebUI) — **ПРОЙДЕН** ✅
> Прервано для перехода в новую беседу (Блок 2: Auth/RBAC).

---

## 🎯 Текущее состояние

| Параметр | Значение |
|----------|----------|
| **Версия** | v3.13.2 |
| **Ветка** | `feature/day_40.4_fragments_export` |
| **Коммит** | `c1debf8` |
| **Пройдено** | ШАГИ 0.0 → 1.21 (Блок 1 — 100%) |
| **Следующий блок** | **Блок 2 — Аутентификация и RBAC** |
| **Найдено багов** | 25+ реальных + 1 false positive |

---

## 📊 Итог Блока 1

| Шаг | Статус |
|-----|--------|
| 0.0 — Проверка окружения | ✅ |
| 1.1-1.3 — Зависимости, ключи, health | ⚠️ BUG-001 |
| 1.4-1.11 — Запуск стека, БД | ⚠️ BUG-002..019 |
| 1.12-1.16 — Сканер, находки | ✅ |
| 1.16.49 — PATCH finding | ✅ |
| 1.16.50 — Bulk update | ✅ |
| 1.16.51 — False positives list | ✅ |
| 1.16.52 — Дедупликация | ✅ |
| 1.17 — WebUI Dashboard | ✅ W-42..46 |
| 1.18 — WebUI Findings | ✅ W-47..53 |
| 1.19 — WebUI Details | ✅ W-54..59 |
| 1.20 — WebUI Catalog + FP | ✅ W-60..73 |
| 1.21 — Smoke-итог | ✅ |

---

## 🔴 Критичные баги (для ТЗ)

### Deploy / Config

| ID | Баг | Файл |
|----|-----|------|
| **BUG-001** | `/api/health` version=3.7.0 (вместо 3.13.2) | `manager/src/main.py` |
| **BUG-002** | Образы `s3-agent:3.5.0` не пересобраны | `docker-compose.yml` |
| **BUG-007** | `.env.example`: VERSION=3.5.0 | `.env.example` |
| **BUG-017/019** | `postgres_exporter` без `networks: [dcap-network]` | `docker-compose.yml:292-311` |
| **BUG-032** | Ключи findings не всегда подхватываются (13.09 — legacy) | `scanner/src/encryption.py` |

### Findings

| ID | Баг | Файл |
|----|-----|------|
| **BUG-022** | Утечка PII через `line_text` / `context_before` / `context_after` — маскируется только `match_text` | `scanner/src/encryption.py` |
| **BUG-034** | Manager не помечает прерванную задачу как `failed` | `manager/src/api/scanner.py` |
| **BUG-035** | Нет батчинга findings при `submit_results` | `scanner/src/managed_scanner.py` |
| **BUG-036** | Emoji во всех `print()`/`logger.*()` — UnicodeEncodeError на cp1251 | вся кодовая база |

### WebUI

| ID | Баг | Серьёзность |
|----|-----|-------------|
| **W-42** | Dashboard: 9 находок вместо 13 | 🔴 |
| **W-54** | `/findings/{id}`: нет кнопок Reveal / PATCH / Fragment | 🔴 блокер |
| **W-55** | Нет `has_encrypted` / `can_reveal` / `fingerprint` в UI | 🔴 |
| **W-56** | `line_text` / `context_*` без маскирования чужих категорий | 🔴 (BUG-022) |
| **W-60** | Catalog tree: `E:` — 0/0, `is_folder: false` | 🔴 |
| **W-66** | FP-страница: файл `—` (нет `file_path`) | 🔴 |
| **W-70** | Нет кнопки «Снять FP» | 🟡 |

### Scanner progress

| ID | Баг | Файл |
|----|-----|------|
| **BUG-027.1** | `progress.total = files_scanned`, `percent: 100` при 70% | `manager/src/api/scanner.py` |
| **BUG-027.2** | Top-level `files_scanned` ≠ `progress.files_scanned` | `manager/src/api/scanner.py` |
| **BUG-027.3** | `status: assigned` при живой задаче | `manager/src/api/scanner.py` |
| **BUG-027.4** | `progress` пустой при `completed` (linewise) | `scanner/src/managed_scanner.py` |

---

## 📊 Открытые наблюдения

### WebUI

- W-43: Footer v3.0.0
- W-44: Сканер `inactive` при работающем heartbeat
- W-47: FP-находки без «Контекст»
- W-48: Тип `credentials` → `Cred`
- W-57: Нет `last_seen_at`/`reviewed_by`/`reviewed_at` в деталях
- W-62: Нет ссылок `/findings/{id}` из каталога
- W-67: FP: `помечено: 1` (user_id вместо username)
- W-72: `last_scanned` не обновляется при повторном скане
- W-73: `classifiers` в `catalog/tree` — не JSON-объект

### Scanner

- W-30: Сканер single-task — нет параллелизма/приоритетов
- W-31: Task 2 висел 2 дня без timeout
- W-35: `much_of_test_files` — не для smoke
- W-36: Методологический — `file_path` в fingerprint без `resource_id`

### False positive (закрыто)

- ~~BUG-028~~ — сканер **корректно находит русский PII** (4762 findings в 15 файлах)
- ~~BUG-025~~ — audit_logs.user="dcap" — psql `user` без кавычек

---

## 🖥️ Окружение

- Windows + PowerShell, Anaconda (`E:\Dev\Anaconda3`)
- Docker Desktop — стек поднят
- AD-DC (`dcap-ad-dc`) — для тестов AD
- Сканер на хосте: `python -X utf8 run_scanner.py scanner/config/scanner_config.json`

### Docker-стек (16 контейнеров)

| Контейнер | Статус |
|-----------|--------|
| dcap-manager | Up (healthy) |
| dcap-webui | Up (healthy) |
| dcap-celery-beat | Up (unhealthy — BUG-004) |
| dcap-celery_worker ×2 | Up (healthy) |
| dcap-celery-exporter | Restarting (BUG-003) |
| dcap-postgres | Up (healthy) |
| dcap-postgres-exporter | Up (unhealthy — BUG-005/017) |
| dcap-redis | Up (healthy) |
| dcap-redis-exporter | Up |
| dcap-prometheus | Up |
| dcap-grafana | Up |
| dcap-alertmanager | Up |
| dcap-flower | Up |
| dcap-s3-agent | Up (старый — BUG-002) |
| dcap-ad-dc | Up (healthy) |

---

## 🐛 Полный список багов

### 🔴 Критичные (10)

- BUG-001: `/api/health` version=3.7.0
- BUG-002/007: Deploy не готов из коробки
- BUG-017/019: `postgres_exporter` без `networks:`
- BUG-022: Утечка PII через `line_text`/`context_*`
- BUG-027.1/2/3/4: Progress-рассинхрон
- BUG-034: Manager не закрывает прерванную задачу
- BUG-035: Нет батчинга findings
- W-42/W-54/W-60/W-66: WebUI-критика

### 🟡 Важные (13)

- BUG-003/004/005/006: Celery-контейнеры
- BUG-009: `.env` не создан
- BUG-012: `docker compose exec` не резолвит
- BUG-015: `init_db.py` смешанный импорт
- BUG-018: Orphan test-контейнеры
- BUG-020/021: Postgres-export, Ctrl+C
- BUG-023/024: FP phone/passport, url/DATABASE_URL
- BUG-036: Emoji во всей кодовой базе
- W-43/W-44/W-47/W-48/W-55/W-57/W-62/W-67/W-70/W-72/W-73

### 🟢 Минорные

- BUG-008, BUG-013, BUG-014
- W-52/W-59/W-63/W-64/W-65/W-68/W-69/W-71

### ❌ False positive

- BUG-025, BUG-028

---

## 🎬 Инструкция для новой беседы

Приложи:
1. Этот файл (STATE_TEST_SESSION.md)
2. STATE.md проекта
3. ROADMAP.md
4. **ТЗ на фикс Блока 1** (см. ниже)

Триггер:
Продолжаем мастер-сессию DCAP v3.13.2.
Приложены: STATE_TEST_SESSION.md, STATE.md, ROADMAP.md, TZ_BLOCK_1_FIX.md.
Блок 1 пройден (1.0 → 1.21).
Следующий блок — Блок 2 (Auth/RBAC).

text

---

## 📊 Что впереди

| Блок | Что | Статус |
|------|-----|--------|
| 1 | Запуск + Smoke | ✅ ПРОЙДЕН |
| 2 | Аутентификация и RBAC | 📋 следующий |
| 3 | Сканер глубоко | 📋 |
| 4 | Findings (API, шифрование, дедуп) | 📋 частично |
| 5 | WebUI | 📋 частично |
| 6-13 | Агенты, Retention, Мониторинг, Безопасность, Нефункциональные, Отказоустойчивость, Интеграция, Регрессия | 📋 |

**Конец STATE_TEST_SESSION.md**