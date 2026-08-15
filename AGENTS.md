# AGENTS.md — DCAP System

Ты — **кодер** (Open Code Desktop + Big Pickle). Твоя задача — писать код строго по ТЗ. Не задавай вопросов, не предлагай улучшений, не анализируй архитектуру. Если что-то непонятно — делай как понял. В отчете давай полный код файлов и команду для коммита.

## Проект

DCAP — система сканирования и аудита данных (PII/credentials/code) на Windows. Компоненты: `manager/` (FastAPI :8000), `scanner/` (агент), `webui/` (дашборд на :8001). Язык кода и коммитов — русский.

## Запуск (локально, из корня репо)

```powershell
python init_db.py                     # создаёт manager/dcap.db
python -m uvicorn manager.src.main:app --port 8000   # Manager + WebUI статика на :8000
python run_webui.py                   # отдельный WebUI на :8001
python run_scanner.py scanner/config/scanner_config.json   # сканер, ждёт Manager на :8000
```

- `Makefile`/`docker-compose` — фикция: `docker-compose.yml` и пакет `shared/` из `manager/Dockerfile` отсутствуют в репо. Реальный флоу — только локальный запуск.
- Для сканера на Windows могут понадобиться `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` (кириллица в консоли). Исторически используется env `/d/dev/anaconda3/python` (Git Bash) с presidio/spacy.

## Важно про WebUI и БД

Manager и WebUI работают с **одной** БД — `manager/dcap.db` (создаётся `init_db.py`):

- Manager — `manager/src/db/session.py` (SQLAlchemy).
- WebUI на :8001 — `webui/api/routes.py` `get_db()` (raw sqlite) пишет/читает тот же `manager/dcap.db`. Задания и ресурсы, созданные через WebUI, сразу видны Manager и сканеру.

Копировать `manager/src/db/dcap.db` не нужно. Корневой `dcap.db` — устаревший/легаси, не трогать.

## Импорты — два стиля, не смешивать

- `manager/src/**` и `webui/**` используют абсолютные импорты `manager.src.*` / `webui.*` — запуск только из корня проекта.
- Корневые утилиты (`init_db.py`, `fix_db.py`, `init_db_data.py`, `test_models.py`, `test_parse.py`) и `manager/src/connectors/permissions/test_collector.py` делают `sys.path.insert(0, "manager/src")` и импортируют верхнеуровнево: `from db.session import ...`, `from connectors.permissions.local import ...`. Не переписывай их на стиль `manager.src.*`.

## Тесты

Pytest отсутствует (папка `manager/tests/` пуста). Тесты — обычные скрипты:

- `python test_models.py` — модели БД.
- `python test_parse.py` — запускает реальный `icacls` (Windows-only).

Инструменты: black (line-length 100), ruff (E,F,W,I), mypy — конфиг в корневом `pyproject.toml`. Готовых команд lint/test в репо нет.

## Структура и границы

- `manager/src/api/` — REST-роутеры (resources, tasks, findings, catalog, scanner, permissions, audit).
- `manager/src/connectors/permissions/` — коллекторы прав (Strategy): `local` (icacls), `remote`, `ad` — заглушка. `services/access_service.py` — логика прав.
- `manager/src/connectors/audit/` — коллектор событий Windows (`windows_audit.py`, wevtutil Security Log). API: `manager/src/api/audit.py` (агентная модель: `POST /api/audit/agents/register`, `/agents/heartbeat`, `/events`; просмотр `GET /api/audit`, `/stats`). Таблицы `audit_agents`/`audit_logs` создаются автоматически (create_all); чтение журнала Security требует прав администратора, иначе агент получит 0 событий.
- `scanner/src/managed_scanner.py` — агент; конфиг `scanner/config/scanner_config.json`; состояние `scanner/state/state.json`.
- `webui/main.py` — актуальный WebUI (весь HTML инлайн в Python). `main_final.py`, `main_simple.py`, `main_static.py` — ❌ устаревшие эксперименты, не трогать. `run_webui.py` запускает именно `webui.main:app`.
- `structure.txt` и `project_context.md` частично устарели — сверяйся с кодом, а не с ними.

## Ограничения платформы

- Нет Active Directory: `ad.py` — заглушка, локальный сбор прав через `icacls` / `net localgroup`.
- Тестовые данные: `D:\Projects\dcap-system\test_files`.

## Git

- Ветки: `master` (стабильная), `develop` (интеграционная), `feature/day_XX` (твоя работа).
- Коммиты: на русском, с префиксом `feat:` (новая фича), `fix:` (исправление), `chore:` (обслуживание).

## Что ты делаешь как кодер

- Получаешь ТЗ от архитектора.
- Генерируешь код по ТЗ.
- Даешь полный код файлов в отчете.
- Даешь команду для коммита.

## Рабочий процесс (кодер ↔ архитектор)

1. Кодер сохраняет обновлённый `AGENTS.md` в корень проекта.
2. Передаёт его агенту (Open Code) как контекст.
3. Архитектор формирует ТЗ на следующий день.
4. Кодер передаёт ТЗ агенту.
5. Кодер проверяет код, тестирует, исправляет.
6. Кодер даёт обратную связь архитектору.

## ТЗ и отчеты

### Где брать ТЗ

- Актуальные ТЗ: `prompts/tz/day_XX_краткое_описание.md`
- После выполнения ТЗ перемещается в `prompts/archive/`

### Где сохранять отчеты

- Отчет: `prompts/reports/day_XX_report.md`
- Формат отчета — см. шаблон в `prompts/tz/tz_template.md`

### Именование

| Что | Формат | Пример |
|-----|--------|--------|
| ТЗ | `day_XX_краткое_описание.md` | `day_15_testing.md` |
| Отчет | `day_XX_report.md` | `day_15_report.md` |

### Процесс

1. Получаешь задание: `prompts/tz/day_XX_*.md`
2. Выполняешь код
3. Сохраняешь отчет: `prompts/reports/day_XX_report.md`
4. Даешь команду для коммита