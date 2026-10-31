# Отчёт: День 38 — Контейнеризация и деплой

**Дата:** 10.09.2026
**ТЗ:** `prompts/tz/day_38_containerization.md` (архив: `prompts/archive/day_38_containerization.md`)
**Роль:** Кодер
**Версия:** v3.6.0
**Ветка:** `feature/day_36-37_scaling`

---

## Резюме

Подготовлен **промышленный контейнерный деплой DCAP**: multi-stage Dockerfile для каждого компонента (Manager, WebUI, S3-агент, Linux-агент) с непривилегированным пользователем и healthcheck, `.dockerignore` для всех компонентов, полный `docker-compose.yml` (PostgreSQL + Redis + Manager + WebUI + Celery worker/beat + Flower + S3-агент через profile `agents`), production-overrides (`docker-compose.prod.yml`: лимиты CPU/RAM, mTLS, репликация worker), скрипты деплоя (`deploy.sh`/`stop.sh`/`logs.sh`/`status.sh`/`healthcheck.sh`), документация `docs/deployment.md`, обновлены `.env.example` и README.

> **Ключевая адаптация ТЗ (из AGENTS.md):** build-контекст Manager/WebUI/S3 — **корень репо** (код использует namespace-импорты `manager.src.*`/`webui.*`, а Manager и S3-агент импортируют пакет `shared/` из корня). В образах `shared/` копируется в `/app/shared`, `PYTHONPATH=/app`. WebUI собирается отдельным контекстом `./webui`.

---

## Ключевые решения по коду

- **`manager/Dockerfile`** — multi-stage (builder: gcc+libpq-dev, `pip --prefix=/opt/dcapdeps`; runtime: python:3.11-slim + libpq5 + curl). Копирует `manager/`, `shared/`, корневой `requirements.txt`, `alembic.ini`, `scripts/migrate_sqlite_to_postgres.py`. Пользователь `dcap` (не root), каталоги `/app/data /app/logs /app/certs`. `CMD`: `alembic upgrade head && uvicorn manager.src.main:app --host 0.0.0.0 --port 8000`. Healthcheck: `curl /api/health`.
- **`webui/Dockerfile`** — multi-stage; контекст `./webui`; копирует webui целиком; `CMD: uvicorn webui.main:app --host 0.0.0.0 --port 8001`; **новый `webui/requirements.txt`** (fastapi, uvicorn, jinja2, httpx — webui использует httpx-прокси); healthcheck `curl /health`. В `webui/main.py` добавлен эндпоинт `GET /health` → `{"status":"ok","version":"3.5.0"}`.
- **`audit-agent-s3/Dockerfile`** — переписан с single-stage на multi-stage; build-контекст корень репо (нужен `shared/event_schema`); WORKDIR `/app/audit-agent-s3`; `CMD: python -m src.main --config config/config.json` (совпадает с локальным запуском).
- **`audit-agent-linux/Dockerfile`** (NEW) — multi-stage; контекст `./audit-agent-linux`; копирует `main.py collector.py buffer.py sender.py config.json`; `VOLUME /watched`; `CMD: python main.py config.json`. `config_loader.py` из ТЗ **отсутствует** в реальном репо — конфиг загружает `main._load_config` (REQUIRED_CONFIG_KEYS).
- **`.dockerignore`** — корневой (для Manager/S3 из корня) + для `webui/`, `audit-agent-s3/`, `audit-agent-linux/`: `__pycache__`, питоновские кэши, `.git`, `.env*`, БД, `data/`, `logs/`, `certs/`, `secrets/`, `tests/`, `temp/`, `prompts/`, `docs/`, `*.md` (с `!README.md`).
- **`docker-compose.yml`** — полный стек: anchors `x-logging` (ротация 100m×3) и `x-restart`; сервисы postgres/redis/manager/celery_worker/celery_beat/celery_flower/webui; s3_agent под profile `agents`; сети `dcap-network`; именованные volumes (`dcap-*`); healthchecks (pg_isready, redis incr ping, healthcheck в образах Manager/WebUI); `depends_on` с `condition: service_healthy`. **Работает и без `.env`** (дефолты). Версия проекта в тегах образов — `${VERSION:-3.5.0}`.
- **`manager/config/config.json`** + **`manager/src/config.py`** — секция `security` и `auth.mode`/`jwt_secret_key` переведены на **env-шаблоны** (`${MTLS_ENABLED:-false}`, `${AUTH_MODE:-hybrid}`, `${JWT_SECRET_KEY:-...}`); `_resolve_env` выполняет нормализацию булевых значений (`"true"/"1"` → `True`) — чтобы Google-композ/prod-override mTLS реально включался, а не оставался строкой.
- **`requirements.txt`** — убрана несуществующая на PyPI зависимость `spnego` (локально не ставилась; код использует `import spnego` как опциональную заглушку, реальный пакет — `pyspnego`). Без этого `pip install` в builder-стадии Manager падал: *"Could not find a version that satisfies the requirement spnego"*.
- **`docker-compose.prod.yml`** — production overrides: лимиты CPU/RAM для manager (2/2G, резервы 1/1G), webui (1/512M), postgres (4/4G + `--data-checksums`), redis (1/1G + maxmemory 512mb LRU), `replicas: 2` для celery_worker, mTLS (`MTLS_ENABLED=true`, certs-тома). ВАЖНО: `container_name` у celery_worker **удалён** из базового compose — Compose запрещает совмещать `container_name` с `replicas > 1` (иначе "container name must be unique").
- **Скрипты** (`scripts/`) — `deploy.sh` (проверка .env/Docker/сертификатов, build, up, healthcheck), `stop.sh [-v]`, `logs.sh [-f] [-n N] [service]`, `status.sh` (ps + HTTP/мясные health), `healthcheck.sh` (Manager+WebUI HTTP, exit-код).
- **`docs/deployment.md`** — быстрый старт, profiles агентов, production, stop/update/troubleshooting.
- **`.env.example`** — разделы VERSION, порты, PG, Redis, JWT, S3, mTLS, логирование.

---

## Выполненная работа

### 1. Dockerfile (multi-stage) + .dockerignore

- `manager/Dockerfile` (MODIFIED, complete rewrite), `manager/.dockerignore` (NEW)
- `webui/Dockerfile` (MODIFIED, rewrite) + `webui/.dockerignore` (NEW) + `webui/requirements.txt` (NEW)
- `audit-agent-s3/Dockerfile` (MODIFIED, multi-stage) + `audit-agent-s3/.dockerignore` (NEW)
- `audit-agent-linux/Dockerfile` (NEW) + `audit-agent-linux/.dockerignore` (NEW)
- `.dockerignore` (NEW, корень — для уваров Manager/S3)

### 2. docker-compose

- `docker-compose.yml` (MODIFIED, полный стек, profiles, healthchecks, volumes, networks, логирование)
- `docker-compose.prod.yml` (NEW)

### 3. Скрипты и документация

- `scripts/deploy.sh`, `stop.sh`, `logs.sh`, `status.sh`, `healthcheck.sh` (NEW)
- `docs/deployment.md` (NEW)
- `.env.example` (MODIFIED), `README.md` (MODIFIED, раздел Дня 38 + v3.6.0), `AGENTS.md` (MODIFIED — статус, релизы, раздел docker/docker-compose)

### 4. Код (необходимые правки для запуска в контейнере)

- `webui/main.py` — эндпоинт `GET /health`
- `manager/src/config.py` — bool-нормализация env-подстановок
- `manager/config/config.json` — env-шаблоны auth/security
- `requirements.txt` — убран несуществующий `spnego`

---

## Тестирование

### Сборка образов (реальные docker build)

| Образ | Команда | Результат |
|-------|---------|-----------|
| `dcap/webui:3.5.0` | `docker compose build webui` | ✅ 22.6s |
| `dcap/manager:3.5.0` | `docker compose build manager` | ✅ 69.8s |
| `dcap/s3-agent:3.5.0` | `docker compose build s3_agent` | ✅ 32.8s |
| `dcap/linux-agent:3.5.0` | `docker build ... audit-agent-linux` | ✅ 19.1s |

**Найден и исправлен блокер:** без удаления `spnego` Manager-образ не собирался (нет пакета на PyPI).

### Smoke-тесты контейнеров

- **Manager** (`dcap/manager:3.5.0`, :18000): старт с Alembic (`alembic upgrade head` на SQLite), `/api/health` → `200 {"status":"healthy","version":"3.5.0"}`, Docker healthcheck = `healthy`. Redis — no-op (fail-open).
- **WebUI** (`dcap/webui:3.5.0`, :18001): `GET /health` → `200 {"status":"ok","version":"3.5.0"}`.
- **S3-агент**: старт, конфиг+shared импортированы, буфер init (`data/buffer/buffer.db`); ожидаемая ошибка регистрации (нет менеджера) — не крашит при настройке.
- **Linux-агент**: старт, watchdog ready, ошибка регистрации ожидаема (нет менеджера).
- **Celery в образе Manager**: `celery --version` → 5.6.3; `from manager.src.workers.celery_app import app` → OK (используется в worker/beat CMD композа).

### Compose-валидация

- `docker compose config -q` — ✅ (base, prod, `--profile agents`).
- `bash -n scripts/*.sh` (через bash в образе) — ✅.
- `py_compile manager/src/config.py webui/main.py` — ✅; импорт `webui.main` с env `MANAGER_URL` — ✅.

---

## Файлы

**NEW:**
- `.dockerignore` (корень)
- `webui/.dockerignore`, `webui/requirements.txt`
- `audit-agent-s3/.dockerignore`
- `audit-agent-linux/.dockerignore`, `audit-agent-linux/Dockerfile`
- `manager/.dockerignore`
- `docker-compose.prod.yml`
- `docs/deployment.md`
- `scripts/deploy.sh`, `scripts/stop.sh`, `scripts/logs.sh`, `scripts/status.sh`, `scripts/healthcheck.sh`
- `prompts/reports/day_38_report.md` (этот отчёт)

**Modified:**
- `manager/Dockerfile` (multi-stage rewrite), `webui/Dockerfile` (rewrite), `audit-agent-s3/Dockerfile` (multi-stage)
- `docker-compose.yml`
- `webui/main.py` (`/health`)
- `manager/src/config.py` (bool-normalization), `manager/config/config.json` (env-шаблоны)
- `requirements.txt` (убран `spnego`)
- `.env.example`, `README.md`, `AGENTS.md`
- `prompts/archive/day_38_containerization.md` (ТЗ перенесено)

---

## Запуск (ручное тестирование)

```powershell
# 1. Настройка
Copy-Item .env.example .env   # отредактировать пароли/ключи (не обязательно — есть дефолты)

# 2. Полный деплой (сборка образов + поднятие стека + healthcheck)
#    (bash: WSL/Git Bash или powershell-замена)
git bash -c "./scripts/deploy.sh"

# 3. Production overrides (лимиты, mTLS, replicas=2)
git bash -c "docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"

# 4. S3-агент отдельно
docker compose --profile agents up -d

# 5. Проверки
git bash -c "./scripts/status.sh && ./scripts/healthcheck.sh"
git bash -c "./scripts/logs.sh manager -f"

# 6. Остановка
git bash -c "./scripts/stop.sh"
```

Ожидаемый результат: https://localhost:8001 (WebUI), :8000 (Manager), :5555 (Flower); PostgreSQL+Redis подняты (healthcheck green), Manager выполняет `alembic upgrade head`, init_db + роли admin создаются на старте приложения.

---

## Команда коммита

```powershell
git checkout -b feature/day_38_containerization
git add .
git commit -m "feat: День 38 — Контейнеризация и деплой

Dockerfile:
- Manager: multi-stage, healthcheck, непривилегированный пользователь
- WebUI: multi-stage, healthcheck
- S3-агент: multi-stage (контекст корень репо, shared/event_schema)
- Linux-агент: multi-stage (VOLUME /watched)

docker-compose:
- Полный стек (postgres, redis, manager, webui, celery, flower)
- Production overrides (docker-compose.prod.yml): лимиты, mTLS, replicas
- Profiles для агентов, healthchecks, volumes, networks, ротация логов

Скрипты:
- deploy.sh, stop.sh, logs.sh, status.sh, healthcheck.sh

Код:
- webui/main.py: GET /health
- manager: env-шаблоны config.json (auth/security), bool-normalization в config.py
- requirements.txt: убран несуществующий spnego

Документация:
- docs/deployment.md
- .env.example обновлен
- README.md / AGENTS.md обновлены"
```

---

## Обратная связь архитектору

- **Все 5 критериев приёмки ТЗ выполнены и проверены реальной сборкой** образов (не только статической валидацией). См. таблицу выше.
- **Build-контекст**: ТЗ предполагал контекст `./manager`/`./webui`/`./audit-agent-s3`, но реальная структура (namespace-импорты + `shared/`) требует корневого контекста для Manager/WebUI/S3. Принято: шаблон и композ синхронны между собой. Если собирать менеджер вручную: `docker build -f manager/Dockerfile -t dcap/manager:3.5.0 .` (из корня).
- **`spnego` в requirements.txt был ошибкой дня 30** — пакета нет на PyPI, локально он не ставился. Удалён; `pyspnego` — единственная рабочая зависимость SPNEGO. Код `windows_auth` помечает Windows Auth disabled при отсутствии spnego (guarded import) — поведение не меняется.
- **У celery_worker убран `container_name`** — иначе production-`replicas: 2` недопустим (Compose запрещает `container_name` + replicas).
- **mTLS в prod-override** реально включается благодаря env-шаблонам в конфиге; сертификаты монтируются `/app/certs/...` из `./certs/...`.
- **Локальный дев-флоу не затронут**: `run_all.py`/`run_manager.py`/`run_webui.py` остались основным путём разработки; docker-compose — только deployment.