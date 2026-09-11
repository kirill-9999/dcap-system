# Развертывание DCAP System (День 38)

Полная контейнеризация всех компонентов: Manager, WebUI, Celery (worker/beat/flower),
PostgreSQL 16, Redis 7, S3/MinIO аудит-агент. Стек поднимается одной командой.

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
├── scanner/Dockerfile          # Scanner (Tesseract + spaCy + Presidio)
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

Примечание: build-контекст для Manager/Scanner/S3-агента — **корень репо**
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
Manager (REST-задания). Запускается через profile `scanner`.

### Запуск

```bash
# Только Scanner
docker compose --profile scanner up -d scanner

# Всё сразу (Scanner + агенты)
docker compose --profile scanner --profile agents up -d
```

### Монтирование папок

По умолчанию Scanner монтирует `${SCAN_PATH}` в `/scanned` (read-only).

Примеры:

```bash
# Linux
SCAN_PATH=/data/shared

# Windows (WSL)
SCAN_PATH=/mnt/c/Data/Shared

# Сетевые папки (сначала монтировать на хосте)
SCAN_PATH=/mnt/smb-share
```

### Ресурсы

| Параметр | Минимум | Рекомендуется |
|----------|---------|---------------|
| CPU      | 2       | 4             |
| RAM      | 4 GB    | 8 GB          |
| Диск     | 10 GB   | 50 GB         |

Размер образа: ~1.5 GB (Tesseract + spaCy + Presidio).

### Troubleshooting

Scanner не видит файлы:

```bash
# Проверить монтирование
docker compose exec scanner ls -la /scanned

# Проверить SCAN_PATH
grep SCAN_PATH .env
```

Scanner не регистрируется:

```bash
# Проверить Manager
docker compose logs manager | grep scanner

# Проверить логи Scanner
docker compose logs scanner
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