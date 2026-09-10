# DCAP Linux Audit Agent — production-образ (multi-stage, День 38).
# Запуск: cd audit-agent-linux && docker build -f Dockerfile -t dcap/linux-agent:3.5.0 .
# Контекст: audit-agent-linux/ (самодостаточный: requirements.txt, main.py, collector.py, buffer.py, sender.py, config.json).

# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

RUN pip install --no-cache-dir --prefix=/opt/dcapdeps -r requirements.txt

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/dcapdeps /opt/dcapdeps
ENV PATH=/opt/dcapdeps/bin:$PATH
ENV PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages

# Код агента (модули верхнего уровня + конфиг)
COPY main.py collector.py buffer.py sender.py ./
COPY config.json .

RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs \
    && chown -R dcap:dcap /app

USER dcap

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Каталог, который агент мониторит (inotify). Монтируется извне (host path).
VOLUME ["/watched"]

CMD ["python", "main.py", "config.json"]