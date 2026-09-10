📋 ТЗ — ДЕНЬ 38: КОНТЕЙНЕРИЗАЦИЯ И ДЕПЛОЙ
Файл: prompts/tz/day_38_containerization.md
Дата: 10.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Подготовить DCAP к промышленному развертыванию:

Dockerfile для каждого компонента (Manager, WebUI, S3-агент, Linux-агент)

Multi-stage сборка — минимальные размеры образов

docker-compose.yml — полный стек одной командой

Volumes и networks — персистентность, изоляция

Скрипты деплоя — deploy.sh, stop.sh, logs.sh, status.sh

Документация — инструкции по развертыванию

.dockerignore — исключение лишних файлов

📁 СТРУКТУРА ИЗМЕНЕНИЙ
text
dcap-system/
├── manager/
│   ├── Dockerfile               # НОВЫЙ: multi-stage
│   └── .dockerignore            # НОВЫЙ
├── webui/
│   ├── Dockerfile               # НОВЫЙ: multi-stage
│   └── .dockerignore            # НОВЫЙ
├── audit-agent-s3/
│   ├── Dockerfile               # ОБНОВИТЬ: multi-stage
│   └── .dockerignore            # НОВЫЙ
├── audit-agent-linux/
│   ├── Dockerfile               # НОВЫЙ
│   └── .dockerignore            # НОВЫЙ
├── docker-compose.yml           # ОБНОВИТЬ: полный стек
├── docker-compose.prod.yml      # НОВЫЙ: production overrides
├── .env.example                 # ОБНОВИТЬ
├── scripts/
│   ├── deploy.sh                # НОВЫЙ: полный деплой
│   ├── stop.sh                  # НОВЫЙ: остановка
│   ├── logs.sh                  # НОВЫЙ: логи
│   ├── status.sh                # НОВЫЙ: статус
│   └── healthcheck.sh           # НОВЫЙ: проверка здоровья
└── docs/
    └── deployment.md            # НОВЫЙ: инструкции по развертыванию
🔧 ДЕТАЛЬНОЕ ТЗ
1. Manager Dockerfile (multi-stage)
dockerfile
# manager/Dockerfile
# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build

# Установка зависимостей для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .

# Установка в отдельную директорию
RUN pip install --no-cache-dir --user -r requirements.txt

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

WORKDIR /app

# Runtime зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование установленных пакетов
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Копирование кода
COPY src/ ./src/
COPY config/ ./config/
COPY alembic.ini .
COPY alembic/ ./alembic/

# Создание непривилегированного пользователя
RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs /app/certs \
    && chown -R dcap:dcap /app

USER dcap

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "manager.src.main:app", "--host", "0.0.0.0", "--port", "8000"]
2. WebUI Dockerfile
dockerfile
# webui/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY src/ ./src/
COPY templates/ ./templates/
COPY config/ ./config/

RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs \
    && chown -R dcap:dcap /app

USER dcap

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

CMD ["python", "-m", "src.main"]
3. S3 Agent Dockerfile
dockerfile
# audit-agent-s3/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs /app/certs \
    && chown -R dcap:dcap /app

USER dcap

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

CMD ["python", "-m", "src.main", "--config", "config/config.json"]
4. Linux Agent Dockerfile
dockerfile
# audit-agent-linux/Dockerfile
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

COPY main.py collector.py buffer.py sender.py config_loader.py ./
COPY config.json .

RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs \
    && chown -R dcap:dcap /app

USER dcap

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Требуется для inotify
VOLUME ["/watched"]

CMD ["python", "main.py", "config.json"]
5. .dockerignore
gitignore
# manager/.dockerignore (аналогично для других)
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.git/
.gitignore
.env
.env.*
*.db
*.sqlite
*.log
logs/
data/
certs/
secrets/
tests/
temp/
prompts/
docs/
*.md
!README.md
6. docker-compose.yml (полный стек)
yaml
# docker-compose.yml
version: '3.8'

x-logging: &default-logging
  driver: "json-file"
  options:
    max-size: "100m"
    max-file: "3"

x-restart: &default-restart
  restart: unless-stopped

services:
  # ===== БАЗА ДАННЫХ =====
  postgres:
    image: postgres:16-alpine
    container_name: dcap-postgres
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-dcap}
      POSTGRES_USER: ${POSTGRES_USER:-dcap}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-dcap123}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-dcap}"]
      interval: 10s
      timeout: 5s
      retries: 5
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== REDIS =====
  redis:
    image: redis:7-alpine
    container_name: dcap-redis
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis123} --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "${REDIS_PORT:-6379}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== MANAGER =====
  manager:
    build:
      context: ./manager
      dockerfile: Dockerfile
    image: dcap/manager:${VERSION:-3.5.0}
    container_name: dcap-manager
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-dcap}:${POSTGRES_PASSWORD:-dcap123}@postgres:5432/${POSTGRES_DB:-dcap}
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      JWT_SECRET_KEY: ${JWT_SECRET_KEY:-change-me-in-production}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    volumes:
      - ./manager/certs:/app/certs:ro
      - manager_data:/app/data
      - manager_logs:/app/logs
    ports:
      - "${MANAGER_PORT:-8000}:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== CELERY WORKER =====
  celery_worker:
    build:
      context: ./manager
      dockerfile: Dockerfile
    image: dcap/manager:${VERSION:-3.5.0}
    container_name: dcap-celery-worker
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-dcap}:${POSTGRES_PASSWORD:-dcap123}@postgres:5432/${POSTGRES_DB:-dcap}
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    command: celery -A manager.src.workers.celery_app:app worker -Q audit_events,scanner_tasks,retention,reports -c 4 --loglevel=info
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== CELERY BEAT =====
  celery_beat:
    build:
      context: ./manager
      dockerfile: Dockerfile
    image: dcap/manager:${VERSION:-3.5.0}
    container_name: dcap-celery-beat
    environment:
      REDIS_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
    command: celery -A manager.src.workers.celery_app:app beat --loglevel=info
    depends_on:
      - redis
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== FLOWER =====
  celery_flower:
    image: mher/flower:latest
    container_name: dcap-flower
    environment:
      CELERY_BROKER_URL: redis://:${REDIS_PASSWORD:-redis123}@redis:6379/0
      FLOWER_PORT: 5555
    ports:
      - "${FLOWER_PORT:-5555}:5555"
    depends_on:
      - redis
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== WEBUI =====
  webui:
    build:
      context: ./webui
      dockerfile: Dockerfile
    image: dcap/webui:${VERSION:-3.5.0}
    container_name: dcap-webui
    environment:
      MANAGER_URL: http://manager:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    ports:
      - "${WEBUI_PORT:-8001}:8001"
    depends_on:
      manager:
        condition: service_healthy
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

  # ===== S3 AGENT =====
  s3_agent:
    build:
      context: ./audit-agent-s3
      dockerfile: Dockerfile
    image: dcap/s3-agent:${VERSION:-3.5.0}
    container_name: dcap-s3-agent
    environment:
      S3_ENDPOINT: ${S3_ENDPOINT:-https://s3.amazonaws.com}
      S3_BUCKET: ${S3_BUCKET:-dcap-logs}
      S3_ACCESS_KEY: ${S3_ACCESS_KEY}
      S3_SECRET_KEY: ${S3_SECRET_KEY}
      MANAGER_URL: http://manager:8000
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
    volumes:
      - s3_agent_data:/app/data
      - s3_agent_logs:/app/logs
    depends_on:
      manager:
        condition: service_healthy
    profiles:
      - agents
    <<: *default-restart
    logging: *default-logging
    networks:
      - dcap-network

networks:
  dcap-network:
    driver: bridge
    name: dcap-network

volumes:
  postgres_data:
    name: dcap-postgres-data
  redis_data:
    name: dcap-redis-data
  manager_data:
    name: dcap-manager-data
  manager_logs:
    name: dcap-manager-logs
  s3_agent_data:
    name: dcap-s3-agent-data
  s3_agent_logs:
    name: dcap-s3-agent-logs
7. docker-compose.prod.yml
yaml
# docker-compose.prod.yml
version: '3.8'

services:
  manager:
    environment:
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      MTLS_ENABLED: "true"
    volumes:
      - ./certs/manager:/app/certs/manager:ro
      - ./certs/ca:/app/certs/ca:ro
      - ./certs/crl:/app/certs/crl:ro
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G

  webui:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M

  postgres:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 4G
    environment:
      POSTGRES_INITDB_ARGS: "--data-checksums"

  redis:
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru

  celery_worker:
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '2'
          memory: 2G
8. scripts/deploy.sh
bash
#!/bin/bash
# scripts/deploy.sh
# Полный деплой DCAP

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "============================================"
echo "  DCAP System — Deployment"
echo "============================================"

# 1. Проверка .env
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Copy .env.example to .env and configure"
    exit 1
fi

# 2. Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose not installed"
    exit 1
fi

# 3. Проверка сертификатов (если mTLS включен)
if grep -q "MTLS_ENABLED=true" .env 2>/dev/null; then
    if [ ! -d "certs/ca" ]; then
        echo "⚠️  mTLS enabled but certificates not found"
        echo "   Run: python scripts/generate_certs.py"
        exit 1
    fi
fi

# 4. Сборка образов
echo ""
echo "📦 Building Docker images..."
docker compose build

# 5. Запуск
echo ""
echo "🚀 Starting services..."
docker compose up -d

# 6. Ожидание готовности
echo ""
echo "⏳ Waiting for services..."
sleep 15

# 7. Проверка статуса
echo ""
echo "📊 Service status:"
docker compose ps

# 8. Healthcheck
echo ""
echo "🏥 Healthcheck..."
./scripts/healthcheck.sh

echo ""
echo "============================================"
echo "  ✅ DCAP deployed successfully!"
echo "============================================"
echo ""
echo "  WebUI:    http://localhost:${WEBUI_PORT:-8001}"
echo "  Manager:  http://localhost:${MANAGER_PORT:-8000}"
echo "  Flower:   http://localhost:${FLOWER_PORT:-5555}"
echo "  Grafana:  http://localhost:${GRAFANA_PORT:-3000}"
echo ""
9. scripts/stop.sh
bash
#!/bin/bash
# scripts/stop.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

REMOVE_VOLUMES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --volumes|-v) REMOVE_VOLUMES=true; shift ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

echo "🛑 Stopping DCAP services..."

if [ "$REMOVE_VOLUMES" = true ]; then
    echo "⚠️  Removing volumes..."
    docker compose down -v
else
    docker compose down
fi

echo "✅ DCAP stopped"
10. scripts/logs.sh
bash
#!/bin/bash
# scripts/logs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

SERVICE=""
TAIL=100
FOLLOW=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow) FOLLOW=true; shift ;;
        -n|--tail) TAIL="$2"; shift 2 ;;
        *) SERVICE="$1"; shift ;;
    esac
done

CMD="docker compose logs --tail=$TAIL"
if [ "$FOLLOW" = true ]; then
    CMD="$CMD -f"
fi
if [ -n "$SERVICE" ]; then
    CMD="$CMD $SERVICE"
fi

$CMD
11. scripts/status.sh
bash
#!/bin/bash
# scripts/status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "============================================"
echo "  DCAP System — Status"
echo "============================================"
echo ""

docker compose ps

echo ""
echo "============================================"
echo "  Health"
echo "============================================"

# Проверка Manager
if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Manager: healthy"
else
    echo "❌ Manager: unhealthy"
fi

# Проверка WebUI
if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
    echo "✅ WebUI: healthy"
else
    echo "❌ WebUI: unhealthy"
fi

# Проверка PostgreSQL
if docker compose exec -T postgres pg_isready -U dcap > /dev/null 2>&1; then
    echo "✅ PostgreSQL: healthy"
else
    echo "❌ PostgreSQL: unhealthy"
fi

# Проверка Redis
if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis: healthy"
else
    echo "❌ Redis: unhealthy"
fi
12. scripts/healthcheck.sh
bash
#!/bin/bash
# scripts/healthcheck.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

ERRORS=0

check_service() {
    local name=$1
    local url=$2
    
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "✅ $name: OK"
    else
        echo "❌ $name: FAILED ($url)"
        ERRORS=$((ERRORS + 1))
    fi
}

echo "🏥 Running healthcheck..."
echo ""

check_service "Manager" "http://localhost:8000/api/health"
check_service "WebUI" "http://localhost:8001/health"

if [ $ERRORS -eq 0 ]; then
    echo ""
    echo "✅ All services healthy"
    exit 0
else
    echo ""
    echo "❌ $ERRORS service(s) failed"
    exit 1
fi
13. .env.example (обновление)
bash
# .env.example

# ===== ВЕРСИЯ =====
VERSION=3.5.0

# ===== ПОРТЫ =====
MANAGER_PORT=8000
WEBUI_PORT=8001
POSTGRES_PORT=5432
REDIS_PORT=6379
FLOWER_PORT=5555
GRAFANA_PORT=3000
PROMETHEUS_PORT=9090

# ===== POSTGRESQL =====
POSTGRES_DB=dcap
POSTGRES_USER=dcap
POSTGRES_PASSWORD=change-me-in-production

# ===== REDIS =====
REDIS_PASSWORD=change-me-in-production

# ===== JWT =====
JWT_SECRET_KEY=change-me-in-production-32-chars

# ===== S3 =====
S3_ENDPOINT=https://s3.amazonaws.com
S3_BUCKET=dcap-logs
S3_ACCESS_KEY=
S3_SECRET_KEY=

# ===== LOGGING =====
LOG_LEVEL=INFO

# ===== MTLS =====
MTLS_ENABLED=false
MTLS_STRICT=false
14. docs/deployment.md
markdown
# Развертывание DCAP System

## Требования

- Docker 20.10+
- Docker Compose 2.0+
- 4 GB RAM (минимум), 16 GB (рекомендуется)
- 2 CPU (минимум), 8 CPU (рекомендуется)
- 20 GB дискового пространства

## Быстрый старт

```bash
# 1. Клонирование
git clone https://github.com/yourusername/dcap-system.git
cd dcap-system

# 2. Настройка
cp .env.example .env
# Отредактируйте .env (пароли, ключи)

# 3. Генерация сертификатов (опционально, для mTLS)
python scripts/generate_certs.py

# 4. Деплой
./scripts/deploy.sh
Проверка
bash
# Статус
./scripts/status.sh

# Healthcheck
./scripts/healthcheck.sh

# Логи
./scripts/logs.sh -f
Production
bash
# С production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
Остановка
bash
# Обычная остановка
./scripts/stop.sh

# С удалением volumes
./scripts/stop.sh --volumes
Обновление
bash
git pull
docker compose build
docker compose up -d
Troubleshooting
Manager не запускается
bash
docker compose logs manager
PostgreSQL не готов
bash
docker compose exec postgres pg_isready -U dcap
Redis недоступен
bash
docker compose exec redis redis-cli ping
text

---

## ✅ КРИТЕРИИ ПРИЕМКИ

### Dockerfile
- [ ] Manager: multi-stage, непривилегированный пользователь, healthcheck
- [ ] WebUI: multi-stage, непривилегированный пользователь, healthcheck
- [ ] S3-агент: multi-stage, непривилегированный пользователь
- [ ] Linux-агент: multi-stage, непривилегированный пользователь
- [ ] .dockerignore для каждого компонента

### docker-compose.yml
- [ ] Полный стек (postgres, redis, manager, webui, celery, flower)
- [ ] Profiles для агентов
- [ ] Healthchecks для всех сервисов
- [ ] Volumes персистентны
- [ ] Networks изолированы
- [ ] Logging с ротацией

### docker-compose.prod.yml
- [ ] Production overrides (лимиты ресурсов)
- [ ] mTLS интеграция
- [ ] Репликация celery worker

### Скрипты
- [ ] `deploy.sh` — полный деплой
- [ ] `stop.sh` — остановка
- [ ] `logs.sh` — логи
- [ ] `status.sh` — статус
- [ ] `healthcheck.sh` — проверка здоровья

### Документация
- [ ] `docs/deployment.md` — инструкции
- [ ] `.env.example` — все переменные
- [ ] README обновлен

---

## 🧪 ТЕСТОВЫЙ СЦЕНАРИЙ

```bash
# 1. Полный деплой
./scripts/deploy.sh

# 2. Проверка статуса
./scripts/status.sh

# 3. Healthcheck
./scripts/healthcheck.sh

# 4. Проверка WebUI
open http://localhost:8001

# 5. Проверка Flower
open http://localhost:5555

# 6. Логи
./scripts/logs.sh manager -f

# 7. Остановка
./scripts/stop.sh
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_38_containerization
git add .
git commit -m "feat: День 38 — Контейнеризация и деплой

Dockerfile:
- Manager: multi-stage, healthcheck, непривилегированный пользователь
- WebUI: multi-stage, healthcheck
- S3-агент: multi-stage
- Linux-агент: multi-stage

docker-compose:
- Полный стек (postgres, redis, manager, webui, celery, flower)
- Production overrides (docker-compose.prod.yml)
- Profiles для агентов
- Healthchecks, volumes, networks

Скрипты:
- deploy.sh, stop.sh, logs.sh, status.sh, healthcheck.sh

Документация:
- docs/deployment.md
- .env.example обновлен
- README.md обновлен"