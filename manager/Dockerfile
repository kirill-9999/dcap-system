FROM python:3.10-slim

WORKDIR /app

# Установка системных зависимостей (wget для healthcheck)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Копируем shared модуль
COPY shared /shared
RUN pip install -e /shared

# Копируем manager
COPY manager/pyproject.toml manager/pyproject.toml
COPY manager/src /app/src

# Установка зависимостей
RUN pip install --no-cache-dir \
    "fastapi>=0.104.0" \
    "uvicorn[standard]>=0.24.0" \
    "grpcio>=1.60.0" \
    "grpcio-tools>=1.60.0" \
    "alembic>=1.12.0" \
    "sqlalchemy>=2.0.25" \
    "psycopg2-binary>=2.9.9" \
    "asyncpg>=0.29.0"

# Скрипт ожидания PostgreSQL (адаптирован для Windows/WSL)
COPY manager/wait-for-postgres.sh /wait-for-postgres.sh
RUN chmod +x /wait-for-postgres.sh

EXPOSE 50051

# Используем wget вместо nc для проверки порта
CMD ["/wait-for-postgres.sh", "postgres", "5432", "--", "python", "-m", "src.main"]