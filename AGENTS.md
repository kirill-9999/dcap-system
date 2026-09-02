# AGENTS.md — DCAP System

Ты — **кодер** (Open Code Desktop + Big Pickle). Твоя задача — писать код строго по ТЗ. Не задавай вопросов, не предлагай улучшений, не анализируй архитектуру. Если что-то непонятно — делай как понял. В отчете давай полный код файлов и команду для коммита. Диалог веди на русском языке.

## Проект

DCAP — система сканирования и аудита данных (PII/credentials/code) на Windows. Компоненты: `manager/` (FastAPI :8000), `scanner/` (агент), `webui/` (дашборд на :8001). Язык кода и коммитов — русский.

## Текущий статус

**Версия:** v3.2.0
**Статус:** ✅ Windows + Linux аудит готов; ✅ Manager/WebUI унифицированы; ✅ Гибридная аутентификация (JWT+Bcrypt/SPNEGO) + роли; ✅ S3/MinIO аудит-агент; ✅ Active Directory интеграция + RBAC WebUI; ✅ Безопасность (mTLS relaxed/strict, CertificateManager, SecretsManager, CRL, docs)
**Следующий этап:** API-ключи для агентов / доработки по приоритету

## Релизы

| Версия | Дата | Описание |
|--------|------|----------|
| v1.0.0 | 2026-07-XX | Базовый функционал |
| v2.0.0 | 2026-08-XX | Управление доступом + Аудит Windows (ядро) |
| v2.0.1 | 2026-08-25 | Windows-стек полностью готов |
| v2.1.0 | 2026-08-27 | Linux-агент + унифицированный формат + WebUI фильтр |
| v3.0.0 | 2026-08-29 | Унификация Manager и WebUI (Вариант А): WebUI — Jinja2 + прокси API на Manager, конфиги портов, run_all.py |
| v3.1.0 | 2026-08-30 | Гибридная аутентификация (JWT + Windows Integrated Auth): режимы local/hybrid/windows_integrated, роли admin/viewer/auditor/scanner, WebUI login |
| v3.1.0+ | 2026-08-31 | S3/MinIO аудит-агент: polling-режим, Server Access Logs (CSV) + MinIO webhook (JSON), конвертация в UnifiedEvent (s3_agent), SQLite-буфер, heartbeat, JWT |
| v3.1.0++ | 2026-09-01 | S3-агент (завершение): нагрузочные тесты, отказоустойчивость (экспоненциальная задержка, throttling), документация, Docker Compose, ротация логов, статус |
| v3.1.0# | 2026-09-01 | Active Directory интеграция + RBAC WebUI (день 33) |
| v3.2.0 | 2026-09-02 | Безопасность (день 34): mTLS (relaxed/strict), CertificateManager, SecretsManager, CRL, generate_certs.py/rotate_certs.py, docker-compose.yml+secrets, SECURITY.md |

## Запуск (локально, из корня репо)

Все компоненты запускаются единообразно скриптами `run_<модуль>.py` из корня репо. Порядок: Manager → WebUI/Scanner/агенты. Компоненты, принимающие конфиг, — конфиг обязателен (без него запуск не происходит).

```powershell
python init_db.py                                  # создаёт manager/dcap.db (первый раз)
python run_all.py                                  # единый запуск Manager (:8000) + WebUI (:8001)
# или по отдельности:
python run_manager.py                              # Manager API на :8000 (порт из конфига)
python run_webui.py                                # WebUI на :8001 (порт из конфига)
python run_scanner.py scanner/config/scanner_config.json   # сканер, ждёт Manager на :8000
python run_audit_agent.py audit-agent-windows/config.json  # Windows-агент аудита (конфиг обязателен)
python run_audit_agent_linux.py ...                       # Linux-агент (см. ниже)
python audit-agent-s3/scripts/start.sh                     # S3/MinIO аудит-агент (daemon, конфиг config/config.json)
# Linux-агент запускается внутри Linux-окружения (см. ниже)
```

- `run_all.py` — единый запуск Manager + WebUI: читает порты из `manager/config/config.json` и `webui/config/config.json`, стартует оба процесса, следит за ними (при падении одного останавливает второй), Ctrl+C — graceful shutdown.
- `run_manager.py` — обёртка над `manager.src.main:app` (uvicorn). Хост/порт читаются из `manager/config/config.json` (секция `server`, дефолт 127.0.0.1:8000).
- `run_webui.py` — обёртка над `webui.main:app` (uvicorn). Хост/порт из `webui/config/config.json` (дефолт 127.0.0.1:8001).
- `run_scanner.py <конфиг>` — сканер (ManagedScanner), конфиг обязателен.
- `run_audit_agent.py <конфиг>` — Windows-агент аудита. Агент не пакет (в `audit-agent-windows/main.py` топ-уровневые импорты collector/buffer/sender), поэтому скрипт добавляет `audit-agent-windows/` в sys.path и вызывает `main.run(config)`. Runtime-данные (`data/state.json`, `data/buffer/`) создаются в `audit-agent-windows/data/` (от `config_path.parent`).
- `run_audit_agent_linux.py` — на Windows выводит подсказку. Реальное использование Linux-агента: `cd audit-agent-linux && ./start.sh --daemon` (или `python main.py config.json`).

- `Makefile`/`docker-compose` — `docker-compose.yml` создан в День 34 (Manager + WebUI + Redis + Docker Secrets + certs-тома), но **полная докеризация образов вторична**: реальный флоу — только локальный запуск (`run_all.py`). Пакет `shared/` из `manager/Dockerfile` отсутствует в репо.
- Для сканера на Windows могут понадобиться `PYTHONUTF8=1` / `PYTHONIOENCODING=utf-8` (кириллица в консоли). Исторически используется env `/d/dev/anaconda3/python` (Git Bash) с presidio/spacy.

## Важно про WebUI и БД

Manager и WebUI работают с **одной** БД — `manager/dcap.db` (создаётся `init_db.py`). С v3.0.0 (День 29.5) прямой доступ WebUI к БД **удалён** — вся работа с данными идёт через Manager:

- Manager — `manager/src/db/session.py` (SQLAlchemy), единственный, кто читает/пишет БД.
- WebUI на :8001 (`webui.main:app`, Jinja2 + `webui/templates/*.html` + `webui/static/`) — рендерит страницы, а все `/api/*` запросы **проксирует** в Manager через `webui/api/routes.py` (httpx-прокси на `MANAGER_URL`, по умолчанию `http://127.0.0.1:8000`). Никаких `sqlite3`-запросов в WebUI нет. Ошибки, JSON и бинарные ответы (отчёты PDF/XLSX) пробрасываются без изменений.
- В Manager добавлены WebUI-совместимые эндпоинты (`manager/src/api/webui.py`): `GET /api/stats`, `GET/POST/DELETE /api/scanners`, `/api/scanners/{id}`, `/api/scanners/{id}/ping`, `GET /api/classifiers`, `POST /api/tasks/create`, `POST /api/resources/create`, `GET /api/access/resources`, `/api/access/resources/{id}/entries`, `/api/access/alerts`, `/api/access/alerts/stats`, `/api/audit/report/preview`, `/api/audit/report/export/excel`, `/api/audit/report/export/pdf`.
- Bootstrap/Font Awesome/Chart.js — локальные копии в `webui/static/vendor/` (без CDN: антивирусы блокируют jsdelivr/cdnjs); WebUI слушает только `127.0.0.1`. Manager на :8000 — чистое API, `/` редиректит на :8001.
- Конфиги: `manager/config/config.json` (секция `server` host/port) и `webui/config/config.json` (секции `server`, `manager.url`, `database`, `logging`). `webui/config.py` — загрузчик со слиянием дефолтов, `utf-8-sig`, env-приоритет.

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
- `shared/event_schema.py` — единая Pydantic-схема `UnifiedEvent` для всех агентов (Windows/Linux/scanner/API).
- `scanner/src/managed_scanner.py` — агент; конфиг `scanner/config/scanner_config.json`; состояние `scanner/state/state.json`.
- `audit-agent-windows/` — лёгкий агент аудита (Windows): `main.py` (цикл), `collector.py` (wevtutil Security Log, XML-парсинг), `buffer.py` (SQLite-буфер), `sender.py` (HTTP в Manager). Конфиг `config.json`; runtime-данные `data/state.json` и `data/buffer/` генерируются при запуске и игнорируются git. Запуск: `python run_audit_agent.py audit-agent-windows/config.json` (или `cd audit-agent-windows; python main.py config.json`). Windows-служба: `service.py` (pywin32, `python service.py install|start|stop|remove`, имя `DCAPAuditAgent`) + бат-файлы `*_service.bat`; логи — `audit-agent-windows/logs/audit_agent.log`. Установка службы требует прав администратора. События отправляются в `POST /api/audit/events` батчами, при недоступности Manager копятся в буфере. Коллектор использует XML-формат (`/f:XML`), colon-syntax параметров, фильтр по EventID в XPath (TimeCreated не работает в wevtutil).
- `audit-agent-linux/` — лёгкий агент аудита (Linux): `main.py` (цикл), `collector.py` (watchdog/inotify + SSH-событии), `buffer.py` (SQLite-буфер), `sender.py`/`heartbeat.py` (HTTP в Manager), `config_loader.py` (конфиг с дефолтами). Конфиг `config.json`; буфер `buffer/` генерируется при запуске. Запуск: `cd audit-agent-linux; ./start.sh --daemon`. Systemd-сервис: `dcap-audit.service` (install: `sudo cp dcap-audit.service /etc/systemd/system/ && sudo systemctl daemon-reload`). Colab-режим: SSH-мониторинг файловой системы через paramiko. Название агента: `dcap-audit-linux-{hostname}` (уникальное). Heartbeat: `POST /api/audit/agents/heartbeat` с `agent_type="linux_agent"`.
- `audit-agent-s3/` — S3/MinIO аудит-агент (Дни 31-32): polling-режим S3-совместимого хранилища (boto3), Server Access Logs (CSV) + MinIO webhook (JSON), конвертация в `UnifiedEvent` (`event_source="s3_agent"`), SQLite-буфер, HTTP-отправка в Manager. Структура: `src/` (`main.py`, `collector.py`, `converters.py`, `buffer.py`, `sender.py`, `state.py`, `heartbeat.py`, `config_loader.py`), `config/config.json` (+`.example`), `docs/` (README, deployment, troubleshooting), `scripts/start.sh|stop.sh|status.sh|restart.sh` (daemon + PID-файл), `tests/unit|integration|load`, `Dockerfile`, `docker-compose.s3.yml` (корень репо), `requirements.txt` (boto3, requests, pydantic, python-dotenv). Запуск: `python audit-agent-s3/scripts/start.sh` (конфиг — env-плейсхолдеры `${VAR:-default}` или `config/config.json`). Агент регистрируется (`/api/audit/agents/register` → `agent_id`, восстанавливается из `data/agent_id.json`), шлёт события на `POST /api/audit/events` с `{agent_id, events:[...]}`; при 401/heartbeat — JWT через `set_token`. `shared/event_schema.py` содержит `"s3_agent"` в Literal `event_source`. Отказоустойчивость (День 32): экспоненциальная задержка в главном цикле (`main.max_error_delay`, дефолт 300с) и в retry-отправке, обработка throttling S3 (`SlowDown`/503), проверка существования бакета и прав чтения, лимит файлов за опрос (`s3.max_files_per_poll`, дефолт 100), батчевые коммиты буфера (`buffer.commit_batch`, дефолт 100) + WAL и индексы, ротация логов (`logging.max_bytes`/`backup_count`), вывод статуса `print_status`. Нагрузочные тесты: `cd audit-agent-s3 && python -m pytest tests/load/ -v` (10 000 событий буфера < 5с, 10 000 CSV < 1с, 1000 событий сериализация < 0.5с).
- `webui/main.py` — актуальный WebUI (Jinja2 + `webui/templates/*.html` + `webui/static/`), единственный UI проекта. `run_webui.py` запускает именно `webui.main:app`. Вся работа с данными — через прокси в Manager (`webui/api/routes.py`), прямого доступа к БД нет.
- `manager/src/auth/` — гибридная аутентификация (День 30): `manager.py` (AuthManager, режимы local/hybrid/windows_integrated), `local_auth.py` (JWT+Bcrypt), `windows_auth.py` (SPNEGO-stub + mock без AD), `jwt.py` (JWTManager, HS256), `models.py` (User/Role + связь user_roles; Bcrypt hash), `schemas.py`, `dependencies.py` (require_auth/require_admin/require_viewer/require_auditor/require_scanner), `middleware.py` (AuthMiddleware), `router.py` (POST /api/auth/login, /mode, /refresh, /logout, /me, /change-password, /users admin, /check), `rate_limit.py`. Защита `/api/*` в middleware; публичные и machine-эндпоинты (агенты/сканер `/api/scanner*`, `/api/audit/agents/*`, `/api/audit/events`) пропускаются без JWT. Роли и дефолтный admin создаются `db/init_roles.py` при старте (admin/admin123 — сменить!). Конфиг auth — `manager/config/config.json` (+env: AUTH_MODE, JWT_SECRET_KEY, AD_*). Для WebUI JWT хранится в localStorage и шлётся заголовком `Authorization: Bearer` (прокси форвардит его в Manager); HttpOnly-cookie Manager'а через прокси не распространяются, поэтому в WebUI используется Bearer-заголовок. После обновления кода обязательно перезапустить Manager — устаревший процесс на :8000 без auth-router возвращает 404.
- `structure.txt` и `project_context.md` частично устарели — сверяйся с кодом, а не с ними.

## Безопасность (День 34)

- **mTLS**: взаимная аутентификация Manager ↔ WebUI ↔ агенты ↔ сканер. Режимы: `relaxed` (по умолчанию — работает на plain HTTP при отсутствии сертификатов) и `strict` (Manager не стартует без PKI).
- **Генерация сертификатов**: `python scripts/generate_certs.py` (чистое Python, cryptography; CA + manager/webui/agents/scanner + CRL; SKI/AKID-расширения обязательны, иначе `Missing Authority Key Identifier`). **Ротация**: `python scripts/rotate_certs.py [--component X]`. Результат — `certs/` (git-ignored).
- **CertificateManager** `manager/src/core/security.py`: загрузка серверного сертификата+CA, `get_server_ssl_context` (uvicorn), `verify_client_cert`, `is_revoked` (CRL). Создаётся в `manager/src/main.py` из секции `security` конфига, передаётся в `AuthMiddleware`.
- **mTLS в Manager**: `run_manager.py` при `mtls_enabled:true` запускает uvicorn с `ssl_*` параметрами, `ssl_cert_reqs=ssl.CERT_OPTIONAL` (relaxed). `AuthMiddleware._check_mtls` для machine-эндпоинтов извлекает клиентский CN, заполняет `request.state.client_cert_cn`; в strict без сертификата — 401.
- **Agents mTLS**: `sender.py` (Windows/Linux/S3) и `ManagerClient` (scanner) читают `cert_path/key_path/ca_path` из конфига; при наличии — `requests.Session.cert/verify`. S3 конфиг — env `MTLS_CERT_PATH/KEY_PATH/CA_PATH`.
- **SecretsManager** `manager/src/core/secrets.py`: приоритет Docker Secrets (`/run/secrets/`) → env → default, кэширование, `get_secrets_manager()` (синглтон).
- **docker-compose.yml** (корень, NEW для дня 34): Manager + WebUI + Redis + Docker Secrets (`jwt_secret_key`, `db_password`, `ad_service_password`) + тома certs. Докеризация образов — вторична (локальный запуск — run_all.py).
- **Конфиг mTLS** — `manager/config/config.json` секция `security`: `{mtls_enabled:false, mtls_strict:false, certs_dir:certs}` (по умолчанию выключено, relaxed). Env: `MTLS_ENABLED`, `MTLS_STRICT`, `CERTS_DIR`.
- **Docs**: `SECURITY.md` (политика), `docs/security_checklist.md` (чеклист production).
- **Тесты**: `python -m pytest manager/tests/test_security.py -v` (CertificateManager, SecretsManager, cert_utils, CRL).

## Ограничения платформы

- Временные файлы/скрипты — только в `D:\Projects\dcap-system\temp` (в .gitignore), не в системном %TEMP%.
- Нет Active Directory: `ad.py` — заглушка, локальный сбор прав через `icacls` / `net localgroup`.
- Тестовые данные: `D:\Projects\dcap-system\test_files`.

## Особенности Windows и wevtutil

- **wevtutil colon-syntax:** параметры только через двоеточие — `/f:XML`, `/q:...`, `/c:N`. Через пробел (`/f XML`) — «слишком много аргументов».
- **wevtutil `/e Events`:** не использовать — вызывает ошибку аргументов. wevtutil отдаёт голые `<Event>` без корневого элемента, парсер оборачивает в `<Events>` автоматически.
- **wevtutil XPath:** `TimeCreated[@SystemTime>='...']` НЕ работает в wevtutil (урезанная XPath 1.0). Фильтр по EventID в XPath, фильтр по времени — в Python.
- **Русская Windows:** Text-вывод wevtutil локализован (`Имя учетной записи:` вместо `SubjectUserName:`). Используйте XML-формат (`/f:XML`) — теги всегда на английском.
- **Служба vs консоль:** CWD службы = `C:\Windows\System32`, не папка проекта. Пути должны быть абсолютными (от `config_path.parent`).
- **SQLite + threading:** всегда `check_same_thread=False` для многопоточных сервисов.
- **CDN:** антивирусы блокируют jsdelivr/cdnjs. Статика (bootstrap, font-awesome, chart.js) — только локально в `webui/static/vendor/`.

## Git

- Ветки: `master` (стабильная), `develop` (интеграционная), `feature/day_XX` (твоя работа).
- Коммиты: на русском, с префиксом `feat:` (новая фича), `fix:` (исправление), `chore:` (обслуживание).

## Что ты делаешь как кодер

- Получаешь ТЗ от архитектора.
- Генерируешь код по ТЗ.
- Даешь полный код файлов в отчете.
- Даешь команду для коммита.
- Даешь инструкцию по запуску для ручного тестирования пользователем

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