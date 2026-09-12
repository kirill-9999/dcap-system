# Развертывание DCAP System (День 38)

Полная контейнеризация компонентов: Manager, WebUI, Celery (worker/beat/flower),
PostgreSQL 16, Redis 7, S3/MinIO аудит-агент. Стек поднимается одной командой.

**Сканер в Docker не запускается** (День 38.5+): задания приходят с путями хоста
(`E:\...`, `/mnt/...`), а контейнер может видеть только заранее смонтированные
тома и не может сам примонтировать папку из задания. Сканер работает **на хосте**
через `python run_scanner.py scanner/config/scanner_config.json` — так он видит
любые пути напрямую (см. раздел «Сканер» ниже).

## Требования

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM (минимум), 16 GB (рекомендуется)
- 2 CPU (минимум), 8 CPU (рекомендуется)
- 20 GB дискового пространства

## Структура

```
dcap-system/
├── Dockerfile                  # (нет) — Dockerfile для каждого компонента:
├── manager/Dockerfile          # Manager + Celery worker/beat
├── webui/Dockerfile            # WebUI
├── audit-agent-s3/Dockerfile   # S3/MinIO аудит-агент
├── audit-agent-linux/Dockerfile# Linux аудит-агент
├── scanner/                    # Scanner (НЕ в Docker, запуск на хосте)
├── .dockerignore               # корневой (для сборки из корня репо)
├── docker-compose.yml          # полный стек
├── docker-compose.prod.yml     # production overrides
├── scripts/
│   ├── deploy.sh               # полный деплой
│   ├── stop.sh                 # остановка
│   ├── logs.sh                 # логи
│   ├── status.sh               # статус + health
│   └── healthcheck.sh          # проверка здоровья
└── docs/deployment.md          # этот файл
```

## Быстрый старт

```bash
# 1. Клонирование
git clone https://github.com/yourusername/dcap-system.git
cd dcap-system

# 2. Настройка
cp .env.example .env
# Отредактируйте .env (пароли PostgreSQL/Redis, JWT_SECRET_KEY, S3 ключи)

# 3. Генерация сертификатов (опционально, для mTLS)
python scripts/generate_certs.py

# 4. Деплой
./scripts/deploy.sh
```

Примечание: build-контекст для Manager/S3-агента — **корень репо**
(компоненты используют пакет `shared/` и/или корневой код импортов),
`webui/Dockerfile` — контекст `./webui`.

## Проверка

```bash
# Статус
./scripts/status.sh

# Healthcheck
./scripts/healthcheck.sh

# Логи
./scripts/logs.sh -f
```

## S3/MinIO аудит-агент (profile)

Агент не входит в базовый стек — запускается через profile `agents`:

```bash
docker compose --profile agents up -d
```

Для него в `.env` заполните `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`.

## Scanner (тяжёлый агент сканирования)

Scanner — агент сканирования файлов (Tesseract, spaCy, Presidio), управляется через
Manager (REST-задания). **Работает на хосте, не в Docker.**

Причина: задания приходят с путями хоста (`E:\shared`, `/mnt/data`, UNC и т.д.).
Docker-контейнер видит только тома, смонтированные при его создании, и не может
сам примонтировать папку из задания. Сканер на хосте видит любые пути напрямую.

### Требования окружения (на хосте)

```bash
python -m pip install -r scanner/requirements.txt
# spaCy модели: python -m spacy download ru_core_news_sm en_core_web_sm
# Windows: apt отсутствует — Tesseract ставится отдельно (см. scanner/README)
```

### Запуск

```bash
# Порядок: сначала Manager (run_all.py / run_manager.py / docker compose up -d), затем сканер
python run_scanner.py scanner/config/scanner_config.json
```

Manager URL задаётся в `scanner/config/scanner_config.json` → `scanner.manager_url`
(по умолчанию `http://localhost:8000`; поддержан env-override `MANAGER_URL`,
`LOG_LEVEL` — см. `scanner/src/config_loader.py`).

Сканер регистрируется в Manager (`/api/scanner/register`), каждые N сек берёт
задание из очереди (`/api/scanner/tasks/pending`), сканирует путь из задания
(доступен напрямую на хосте), отправляет результаты
(`/api/scanner/tasks/{id}/results`). При недоступности Manager результаты
сохраняются в `scanner/data/offline/` и автоматически досылаются.

### Ресурсы

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| CPU      | 2       | 4             |
| RAM      | 4 GB    | 8 GB          |
| Диск     | 10 GB   | 50 GB         |

### Troubleshooting

Scanner не регистрируется:

```bash
# Проверить, что Manager поднят и виден
curl http://localhost:8000/api/health

# Проверить логи сканера
tail -f logs/scanner.log
```

## Production

```bash
# С production overrides (лимиты ресурсов, mTLS, репликация worker)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Prod-надстройка добавляет:
- ограничения CPU/RAM для manager/postgres/redis/webui/celery_worker;
- лимиты для сервисов мониторинга (prometheus/grafana/alertmanager/exporters);
- `POSTGRES_INITDB_ARGS=--data-checksums`;
- `--maxmemory 512mb --maxmemory-policy allkeys-lru` для Redis;
- `replicas: 2` для celery_worker;
- mTLS (при включенном `MTLS_ENABLED=true` и наличии `certs/`).

## Мониторинг (День 39)

Стек мониторинга поднимается вместе с остальными сервисами:

```bash
docker compose up -d prometheus grafana alertmanager \
  postgres_exporter redis_exporter celery_exporter
```

- **Grafana** — http://localhost:3000 (`admin` / `${GRAFANA_PASSWORD}`, дефолт `admin`);
- **Prometheus** — http://localhost:9090;
- **Alertmanager** — http://localhost:9093.

Scaner отдаёт метрики на :9101 **с хоста** (он не в Docker) — Prometheus
собирает через `host.docker.internal:9101` (для Linux-хостов в compose
сервиса prometheus добавлен `extra_hosts`).

Полная документация мониторинга — [docs/monitoring.md](monitoring.md).

## Тестирование (День 40-41)

Изолированный тестовый стек (`docker-compose.test.yml`, БД `dcap_test`, tmpfs,
Manager :18000, WebUI :18001) и набор pytest-тестов — E2E / Chaos / Load.

```bash
pip install -r requirements-dev.txt
./scripts/test-up.sh       # поднять тестовый стек
pytest tests/              # все тесты
./scripts/run-tests.sh e2e # E2E (также: chaos, load, quick, all)
./scripts/test-down.sh     # остановить стек
```

Полная документация тестирования — [docs/testing.md](testing.md).

## Ключи шифрования находок (День 40.1)

С v3.9.0 находки хранятся в зашифрованном виде (AES-256-GCM) + HMAC-fingerprint.
Перед **первым** запуском сгенерируйте ключи и передайте их в Manager:

```bash
python scripts/generate_findings_keys.py   # создаёт secrets/findings_*
```

Сгенерированные файлы (в `secrets/`, не коммитятся):
- `findings_encryption_key` — base64-кодированные 32 байта (AES-256);
- `findings_hmac_key` — base64-кодированные 32 байта (HMAC-SHA256 для fingerprint);
- `findings_key_id` — идентификатор ключа (например, `key-2026-09`).

Передача в Manager (приоритет):
1. **Docker Secrets** — `/run/secrets/findings_*` (compose-mount, см. `docker-compose.yml`);
2. **env** — `FINDINGS_ENCRYPTION_KEY`, `FINDINGS_HMAC_KEY`, `FINDINGS_KEY_ID`.

Dev-режим без ключей работает, но ключи генерируются каждый запуск
(ephemeral) — расшифровка после перезапуска невозможна. Для локальной разработки
установите env-переменные или прогоните `generate_findings_keys.py` и добавьте
`secrets/` в монтирование.

Ротация ключей: сгенерируйте новые и обновите секреты — старые значения
перешифровать нельзя (AES-GCM с одноразовым nonce), новые находки будут
шифроваться новым ключом.

### Ключи шифрования сканера (День 40.2)

С v3.10.0 сканер шифрует и маскирует находки **на стороне сканирующего хоста** —
открытый текст не покидает хост. Ключи должны **совпадать** с ключами Manager
(тот же `FINDINGS_ENCRYPTION_KEY`), иначе Manager не расшифрует `match_text`.

Передайте их сканеру (приоритет: Docker Secrets → env):

```bash
export FINDINGS_ENCRYPTION_KEY=<base64 32 bytes>   # тот же, что у Manager
export FINDINGS_HMAC_KEY=<base64 32 bytes>
export FINDINGS_KEY_ID=key-2026-09                 # должно совпадать с key_id у Manager
```

Один набор можно получить через `python scripts/generate_findings_keys.py` —
файлы из `secrets/` подойдут обоим компонентам (Docker Secrets для Manager,
env для сканера на хосте).

Если ключи **не заданы** — сканер работает в **legacy-режиме**: шлёт открытый
текст, Manager шифрует сам. Работает с любым Manager, но открытый текст идёт
по сети (менее безопасно; рекомендуется задать ключи).

## WebUI: находки и каталог (День 40.3)

WebUI переведён на строчную модель находок (v3.10+). Все данные — через прокси
на Manager (`webui/api/routes.py`, catch-all `/api/*`), прямого доступа к БД нет.

- **`/findings`** — список находок (`webui/templates/findings.html`,
  `webui/static/js/findings.js`): фильтры по статусу/типу/категории/severity/задаче,
  bulk-действия (подтвердить/ложное), пагинация prev/next, экспорт отфильтрованного
  списка в JSON. Поля — новое представление (`finding_type`, `match_text` masked,
  `file_path:line_number`, `first_seen_at`, `confidence`, `status`).
- **`/findings/{id}`** (40.3.2) — детальная карточка
  (`finding_detail.html`, `finding_detail.js`): фрагмент кода, контекст, reveal
  (`POST /api/findings/{id}/reveal`, доступен auditor/admin, действие логируется),
  кнопки «Подтвердить» и «Ложное срабатывание» с комментарием.
- **`/catalog`** (40.3.3) — каталог находок по файлам (`catalog.js`): дерево
  папка → файл → найденные строки, поиск и фильтр по типу, строится клиентски
  из `GET /api/findings?limit=1000`.
- **`/false-positives`** — журнал ложных срабатываний
  (`false_positives.html`, `false_positives.js`): `GET /api/findings/false-positives`,
  доступ auditor/admin.
- **Прогресс сканера** на дашборде: карточка «Сканеры» показывает
  `current_task.progress` (files_scanned/total/percent) из heartbeat
  (`manager/src/api/webui.py` `_scanner_dict(s, db)`, JSON-колонка `scan_tasks.progress`).

`webui/static/js/api.js` — общий HTTP-клиент: `request()`, `get`/`post`/`patch`/`delete`,
разбор `{detail}` ошибок, авто-редирект на `/login` при 401, `showSuccess`/`showError`.

### Фрагменты и экспорт находок (День 40.4)

- `GET /api/findings/{id}/fragment` — фрагмент находки (Viewer+):
  - `image_region` → PNG: готовый фрагмент из `fragment_path` или crop по
    `bounding_box` через Pillow (`manager/src/core/image_fragment.py`), кэшируется;
    заголовок `X-Bounding-Box`.
  - `?format=hex` (`byte_range`) → текстовый hex-дамп вокруг `byte_offset` с окном
    ±64 байта (`manager/src/core/hex_dump.py`); готовый `hex_preview` отдаётся как есть.
  - `text_line`/`text_context` → `400` (текст отдаётся в `/api/findings/{id}`).
  - `category=person` (PII без маски) → `403` для не-Auditor.
- `GET /api/findings/export?format=csv|json` — экспорт находок (Auditor+):
  - По умолчанию **маскированное**; `?reveal=true` — расшифровка (Auditor+),
    действие логируется в `audit_logs` (`findings_exported`).
  - Фильтры: `status`, `finding_type`, `category`, `severity`, `task_id`, `resource_id`.
  - CSV: BOM для Excel, `Content-Disposition: attachment`, защита от CSV injection
    (`manager/src/core/csv_utils.py` — префикс `'` для `=`, `+`, `-`, `@`, TAB, CR).
- Прокси WebUI (`webui/api/routes.py`) пробрасывает бинарные ответы и
  `Content-Disposition: attachment` как есть — кнопка «Экспорт» на странице находок
  скачивает файл через браузер.
- `GET /api/findings` возвращает заголовок `X-Total-Count` (всего найдено с фильтрами);
  WebUI использует его для постраничной навигации с номерами страниц.

## Остановка

```bash
# Обычная остановка
./scripts/stop.sh

# С удалением volumes (все данные БД и логи удаляются!)
./scripts/stop.sh --volumes
```

## Обновление

```bash
git pull
docker compose build
docker compose up -d
```

## Linux аудит-агент (docker)

Образ: `cd audit-agent-linux && docker build -f Dockerfile -t dcap/linux-agent:3.5.0 .`

Запуск: `docker run -d --name dcap-linux-agent -v /path/to/watch:/watched \
  -e MANAGER_URL=http://manager:8000 dcap/linux-agent:3.5.0`

Внимание: дефолтный `config.json` агента указывает `watch_paths: ["/home/kirill/test_audit"]` —
замените его на свой (монтируйте поверх `/app/config.json`), либо используйте
`docker run -v ./audit-agent-linux/config.json:/app/config.json:ro ...`.

## Troubleshooting

### Manager не запускается

```bash
docker compose logs manager
```

### PostgreSQL не готов

```bash
docker compose exec postgres pg_isready -U dcap
```

### Redis недоступен

```bash
docker compose exec redis redis-cli ping
```

### Alembic-миграции при первом старте

`:8000/api/health` отвечает 500? Manager при старте выполняет
`alembic upgrade head`. Проверьте логи:

```bash
docker compose logs manager | grep -i alembic
```

При необходимости выполните вручную:
`docker compose exec manager alembic upgrade head`