# Отчёт: День 29.5 — Унификация Manager и WebUI (Вариант А)

**Дата:** 29.08.2026
**ТЗ:** `prompts/tz/day_29.5_manager_webui_unification.md`
**Роль:** Кодер

---

## Резюме

Выполнена унификация Manager и WebUI по Варианту А: устранено дублирование БД и API. WebUI на :8001 (`webui.main:app`, Jinja2) теперь **проксирует** все `/api/*` запросы в Manager через `webui/api/routes.py` (httpx, без прямого доступа к БД). В Manager добавлены WebUI-совместимые эндпоинты и аддитивные правки форматов. Введены конфиги `manager/config/config.json` + `webui/config/config.json` (порты серверов), обновлён запуск: `run_all.py` (единый), `run_manager.py`/`run_webui.py` читают порты из конфигов. Обновлены AGENTS.md / README.md / project_plan.md.

---

## Выполненная работа

### 1. Конфиги компонентов

- **`manager/config/config.json`** — секция `server` (host 127.0.0.1, port 8000), `database` (sqlite:///manager/dcap.db), `webui` (enabled), `logging`. (Создан — ранее отсутствовал.)
- **`webui/config/config.json`** — секции `server` (host 127.0.0.1, port 8001), `manager.url` (`http://127.0.0.1:8000`), `database`, `logging`. (Создан.)
- **`webui/config.py`** — переписан: VERSION 3.0.0, глубокая загрузка из `webui/config/config.json` (`utf-8-sig`), слияние с дефолтами, env-приоритет; добавлены `MANAGER_URL`, `LOG_LEVEL`; `WEBUI_HOST`/`WEBUI_PORT`/`DEBUG` из конфига. Решение: `webui/config.py` **оставлен** (не удалять), пакет `shared/*` не создавался.

### 2. Manager — WebUI-совместимые эндпоинты

Новый роутер `manager/src/api/webui.py` (подключён в `manager/src/main.py`), все аддитивные:

- `GET /api/stats`
- `GET /api/scanners`, `GET /api/scanners/{id}`, `POST /api/scanners/{id}/ping`, `DELETE /api/scanners/{id}`
- `GET /api/classifiers`
- `POST /api/tasks/create`
- `POST /api/resources/create`
- `GET /api/access/resources`, `GET /api/access/resources/{id}/entries`, `GET /api/access/alerts`, `GET /api/access/alerts/stats`, `PUT /api/access/alerts/{alert_id}`
- `POST /api/audit/report/preview`, `POST /api/audit/report/export/excel`, `POST /api/audit/report/export/pdf` (openpyxl + reportlab)

Правки форматов в существующих роутерах (аддитивно, шаблоны не менялись):

- `manager/src/api/findings.py` — `GET /api/findings/count` перенесён **перед** динамическим `/api/findings/{finding_id}` (фикс 422, был затенён).
- `manager/src/api/audit.py` — в `GET /api/audit/stats` добавлены `by_source`, `agents_total`, `agents_online`.
- `manager/src/api/resources.py` — в список ресурсов добавлен `created_at`; в `POST /api/resources/{id}/scan` — `"success": True` (resources.html проверяет `res.success`/`res.task_id`).

### 3. WebUI — чистый прокси на Manager

`webui/api/routes.py` переписан полностью (1456 строк raw-sqlite-дублей → ~80 строк прокси):

- `APIRouter(prefix="/api")` с catch-all `/{path:path}` на GET/POST/PUT/DELETE/PATCH.
- Каждый запрос транслируется в `{MANAGER_URL}/api/{path}` с телом и query-параметрами.
- Ошибки Manager (404/422/…), JSON-ответы пробрасываются без изменений; бинарные ответы (`content-disposition: attachment`, PDF/XLSX) — через `StreamingResponse`.
- При недоступности Manager — `503`, при таймауте — `504`.
- `webui/api/schemas.py` остался неиспользуемым (не импортируется), чистка не требуется.

### 4. Запуск

- **`run_all.py`** (новый) — единый запуск Manager + WebUI: читает порты из обоих конфигов, стартует `run_manager.py` и `run_webui.py`, следит за процессами (падение одного останавливает второй), Ctrl+C — graceful shutdown.
- **`run_manager.py`** — читает host/port из `manager/config/config.json`.
- **`run_webui.py`** — читает host/port из `webui/config/config.json`.

### 5. Документация

- **AGENTS.md** — версия v3.0.0, релизы, раздел «Запуск» (run_all.py, порты из конфигов), переписан раздел «Важно про WebUI и БД» (WebUI = Jinja2 + templates + static + прокси, без sqlite), обновлён раздел «Структура и границы».
- **README.md** — компоненты (WebUI: Jinja2 + прокси), запуск (run_all.py/run_manager.py/run_webui.py), архитектура, версии.
- **project_plan.md** — версия v3.0.0, статусы Дней 29/29.5, новый раздел «Унификация Manager и WebUI».

---

## Верификация

- Все `.py`-файлы (10 затронутых) компилируются (py_compile: 0 ошибок).
- End-to-end (TestClient WebUI-прокси против реального живого Manager на изолированном порту 8010/8011):
  - GET: `/api/stats`, `/api/scanners`, `/api/classifiers`, `/api/findings`, `/api/audit`, `/api/audit/stats`, `/api/audit/agents`, `/api/catalog`, `/api/catalog/stats`, `/api/access/alerts/stats`, `/api/resources` — **все 200**.
  - POST: `/api/audit/report/preview` — 200 (реальные данные, body round-trip); `/api/scanners/999/ping` — 404 проброшена корректно.

---

## Итоговый чеклист

- [x] Конфиги `manager/config/config.json` + `webui/config/config.json`
- [x] `webui/config.py` переписан (дефолты + json + env-приоритет)
- [x] Manager: WebUI-совместимые эндпоинты (`manager/src/api/webui.py`) + фиксы форматов
- [x] WebUI → чистый прокси `/api/*` на Manager (без доступа к БД)
- [x] `run_all.py`, `run_manager.py`/`run_webui.py` из конфигов
- [x] Обновлены AGENTS.md / README.md / project_plan.md
- [x] Верификация end-to-end (все 200)
- [x] Отчёт сохранён
- [x] ТЗ перемещено в `prompts/archive/`

---

## Примечания / известные ограничения

1. **docker-compose пропущен** — в ТЗ отражён как фикция: `docker-compose.yml` и пакет `shared/` из `manager/Dockerfile` отсутствуют в репо. Реальный флоу — только локальный запуск. Факт зафиксирован.
2. **`webui/api/schemas.py`** остался в репо, но больше не импортируется (был для raw-sqlite-дублей). Не мешает, не удалён.
3. **Конфиг с дефолтами:** в отличие от агентов, у Manager/WebUI конфиг не обязателен — при отсутствии используются дефолты (8000/8001). Это соответствует ТЗ и запуску `run_all.py`.
4. **Старые процессы** (Manager :8000 / WebUI :8001, запущенные до рефакторинга) продолжат работать на старом коде до перезапуска. Для применения изменений необходима остановка и повторный запуск через `python run_all.py`.
5. **Пути-конфликт `/api/findings/count`** был причиной 422 — устранён переносом маршрута в `manager/src/api/findings.py` перед динамическим.

---

## Команда коммита

```powershell
git add -A
git commit -F temp\commit_msg.txt
```

Сообщение коммита (`temp/commit_msg.txt`):
```
feat: унификация Manager и WebUI — WebUI как прокси на Manager (день 29.5)

- webui/api/routes.py: raw sqlite-дубли удалены, /api/* полностью проксируется
  в Manager (httpx), JSON/ошибки/бинарные ответы без изменений
- manager/src/api/webui.py: WebUI-совместимые эндпоинты (/api/stats,
  /api/scanners, /api/classifiers, /api/tasks/create, /api/resources/create,
  /api/access/*, /api/audit/report/*)
- правки форматов: findings/count перед динамическим маршрутом (фикс 422),
  audit/stats + by_source/agents_total/agents_online, created_at и success в ресурсах
- конфиги server-портов: manager/config/config.json и webui/config/config.json;
  webui/config.py переписан (дефолты + json + env-приоритет)
- run_all.py единый запуск; run_manager.py/run_webui.py читают порты из конфигов
- обновлены AGENTS.md, README.md, project_plan.md
```
