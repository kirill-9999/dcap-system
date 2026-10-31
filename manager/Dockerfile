# DCAP Manager — production-образ (multi-stage, День 38).
# Запуск: docker build -f manager/Dockerfile -t dcap/manager:3.5.0 .
#
# ВАЖНО: build-контекст — КОРЕНЬ репозитория (нужен пакет shared/ + root requirements.txt).

# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build

# Системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей (root requirements.txt покрывает Manager)
COPY requirements.txt .

# Установка в отдельный префикс (нейтральный путь, доступен непривилегированному пользователю)
RUN pip install --no-cache-dir --prefix=/opt/dcapdeps -r requirements.txt

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

WORKDIR /app

# Runtime-зависимости (libpq5 для psycopg2, curl для HEALTHCHECK)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование установленных пакетов
COPY --from=builder /opt/dcapdeps /opt/dcapdeps
ENV PATH=/opt/dcapdeps/bin:$PATH
ENV PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages:/app

# Копирование кода (пакеты manager.* и shared.* — namespace-импорты из корня)
COPY manager/ ./manager/
COPY shared/ ./shared/
COPY alembic.ini .
# Утилита переноса данных SQLite -> PostgreSQL
COPY scripts/migrate_sqlite_to_postgres.py ./scripts/migrate_sqlite_to_postgres.py

# Создание непривилегированного пользователя + рабочие каталоги
RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs /app/certs \
    && chown -R dcap:dcap /app

USER dcap

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Healthcheck (Manager отдаёт /api/health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

EXPOSE 8000

# Старт: применённые миграции (Alembic) + Manager
CMD ["sh", "-c", "alembic upgrade head && uvicorn manager.src.main:app --host 0.0.0.0 --port 8000"]