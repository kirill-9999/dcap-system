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
- `POSTGRES_INITDB_ARGS=--data-checksums`;
- `--maxmemory 512mb --maxmemory-policy allkeys-lru` для Redis;
- `replicas: 2` для celery_worker;
- mTLS (при включенном `MTLS_ENABLED=true` и наличии `certs/`).

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