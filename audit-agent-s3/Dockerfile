# DCAP S3/MinIO Audit Agent — production-образ (multi-stage, День 38).
# Запуск: docker build -f audit-agent-s3/Dockerfile -t dcap/s3-agent:3.5.0 .
# ВАЖНО: build-контекст — КОРЕНЬ репозитория (нужен пакет shared/event_schema).
# Запуск из каталога сборки: cd audit-agent-s3 && docker build -f Dockerfile ..  (shared в контексте)

# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build

COPY audit-agent-s3/requirements.txt ./requirements.txt

RUN pip install --no-cache-dir --prefix=/opt/dcapdeps -r requirements.txt

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/dcapdeps /opt/dcapdeps
ENV PATH=/opt/dcapdeps/bin:$PATH
ENV PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages:/app

# Код агента
COPY audit-agent-s3/src ./audit-agent-s3/src
COPY audit-agent-s3/config ./audit-agent-s3/config
COPY audit-agent-s3/scripts ./audit-agent-s3/scripts
# Общий пакет shared/ (event_schema, импортируется src/*)
COPY shared ./shared

RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/audit-agent-s3/data /app/audit-agent-s3/logs \
    && chown -R dcap:dcap /app \
    && mkdir -p /app/audit-agent-s3/data/state /app/audit-agent-s3/data/buffer \
    && chown -R dcap:dcap /app/audit-agent-s3/data

# Рабочий каталог — корень агента (python -m src.main, конфиг config/config.json)
WORKDIR /app/audit-agent-s3

USER dcap

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

CMD ["python", "-m", "src.main", "--config", "config/config.json"]