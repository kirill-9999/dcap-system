# AGENTS.md — DCAP (инструкция кодеру)

## Роль

Ты — кодер (Open Code Desktop + Big Pickle). Пиши код строго по ТЗ.
Не задавай вопросов, не предлагай улучшений, не анализируй архитектуру. Если что-то непонятно — делай как понял.
В отчёте: полный код файлов + команда `git commit` + инструкция ручного теста.
Язык диалога, кода, коммитов — русский.

## Проект (кратко)

DCAP — аудит данных (PII/credentials/code) на Windows/Linux.
`manager/` (FastAPI :8000) · `scanner/` (host-only, `run_scanner.py`) · `webui/` (Jinja2 + прокси API :8001).
Архитектура, модели, API — `ARCHITECTURE.md`. План/бэклог — `ROADMAP.md`. Текущее состояние — `STATE.md`.

## Документы

| Файл | Кто | Когда |
|------|-----|-------|
| STATE.md | кодер | в конце дня |
| ROADMAP.md | архитектор | план/бэклог |
| ARCHITECTURE.md | архитектор | при изменениях |
| AGENTS.md | архитектор | редко |

Старые `project_plan.md` / `project_context.md` удалены — не создавать.

## Рабочий цикл

1. ТЗ: `prompts/tz/day_XX_*.md`.
2. Код → отчёт: `prompts/reports/day_XX_report.md` (шаблон `prompts/tz/tz_template.md`).
3. Коммит: `feat|fix|chore: День XX — <кратко> (vX.Y.Z)`. Доки (`STATE.md` и пр.) можно отдельным коммитом `docs: ...`.
4. Обновить `STATE.md` (поля: Обновлено, Версия, Статус, Текущий день, Следующий шаг, строка в «Выполненные дни», открытые проблемы, последние использованные файлы).
5. ТЗ → `prompts/archive/`; старые дампы — туда же.

## Текущий статус

**Версия:** v3.14.3. Детали и следующий шаг — в `STATE.md`.

## Текущий спринт

**v3.14.4 (UI hotfix)** — ТЗ: `prompts/tz/day_53_4f_ui_hotfix.md`.
6 задач: BUG-265/266/267 (dashboard RBAC + 403-спам), BUG-270/271 (users responsive), BACKLOG-324 (findings-фильтры).
Отчёт: `prompts/reports/day_53_4f_ui_hotfix_report.md`.

**После v3.14.4:** Retention (Блок 18) → 55 (GitHub) → 56 (BUG-117) → 57 (релиз v3.0.0).

## Запуск (локально, из корня репо)

```powershell
python init_db.py                                    # создаёт manager/dcap.db (первый раз)
python run_all.py                                    # Manager :8000 + WebUI :8001
python run_manager.py                                # Manager отдельно
python run_webui.py                                  # WebUI отдельно
python run_scanner.py scanner/config/scanner_config.json   # сканер (host-only)
python run_audit_agent.py audit-agent-windows/config.json  # Windows-агент (конфиг обязателен)
python audit-agent-s3/scripts/start.sh               # S3/MinIO-агент (daemon)
# Linux-агент — внутри Linux: cd audit-agent-linux && ./start.sh --daemon
Предупреждение: сканер на Windows может требовать PYTHONUTF8=1 / PYTHONIOENCODING=utf-8 (кириллица в консоли).

Тест-стенд (E2E)
powershell
docker compose -p dcap-test -f docker-compose.test.yml up -d --wait   # Manager :18000, WebUI :18001
pytest tests/e2e -q --basetemp="E:\projects\dcap-system\.pytest-tmp"  # Windows: pytest-current лочится (BUG-260)
⚠️ docker-compose.test.yml имеет name: dcap-test (BACKLOG-317). Не запускать down -v --remove-orphans из него против основного стека (:8000/:8001) — общее имя проекта снесёт контейнеры dcap-*.

Грабли (короткий список)
WebUI без БД: все /api/* — прокси в Manager (webui/api/routes.py). Прямого sqlite нет.

RBAC: у Manager-эндпоинтов роли; viewer НЕ имеет прав на /api/audit/* → 403. Фронт (dashboard.js и пр.) должен проверять роль (Auth.hasRole) до вызова, а не спамить 403.

api.js 403 → toast «Недостаточно прав» + редирект (BUG-256). console.warn только для !== 403 (BUG-266) — иначе спам в консоли.

/settings auth_mode — read-only (BUG-187): не редактировать (иначе лок-аут без AD). UI — только индикатор + предупреждение.

Импорты не смешивать: manager.src.* / webui.* — абсолютные (запуск из корня). Корневые утилиты (init_db.py, test_*.py) и permissions/test_collector.py — sys.path.insert(0, "manager/src") + верхнеуровневые.

PG: сначала alembic upgrade head, потом scripts/migrate_sqlite_to_postgres.py.

Windows/wevtutil: colon-syntax (/f:XML), без /e, XML-формат (русская локаль ломает Text), TimeCreated в XPath не работает — фильтр в Python. Служба: CWD = System32 → абсолютные пути от config_path.parent.

SQLite + threads: check_same_thread=False.

CDN запрещён (антивирусы) — только webui/static/vendor/.

Временные файлы: только E:\projects\dcap-system\temp (в .gitignore), не в системном %TEMP%. Тестовые данные — test_files/.

Auth: дефолт admin/admin123; JWT в WebUI — Bearer в localStorage (не cookie). После правок кода перезапустить Manager.

Scanner — на хосте (run_scanner.py), не в Docker: контейнер не видит пути из заданий.

Тесты
Unit: pytest tests/unit manager/tests -q → 517 passed (53.4f). После v3.14.4 → ожидается 521+ (добавятся test_dashboard_v3144.py — 4 теста). Корневой conftest.py переносит basetemp в .pytest-tmp/ (Windows).

E2E: tests/e2e (стенд :18000/:18001). Без предусловий — 48 passed / 12 skipped / 5 failed; эталон 53/7 при предусловиях (сканер :9101, MinIO :9000, seed-findings, auditor). См. docs/testing.md.

Скрипты: python test_models.py, python test_parse.py (Windows, реальный icacls); security — pytest manager/tests/test_security.py.

Инструменты: black (line-length 100), ruff (E,F,W,I), mypy — конфиг в корневом pyproject.toml. Готовых команд lint в репо нет.

Git
Ветки: master (стабильная) · develop (интеграционная) · feature/day_XX (рабочая).
Коммиты на русском с префиксом feat: / fix: / chore:.

Границы
Состав компонентов, агенты, эндпоинты и схемы данных — в ARCHITECTURE.md. Не дублировать их здесь.