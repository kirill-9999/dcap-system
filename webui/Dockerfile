# DCAP WebUI — production-образ (multi-stage, День 38).
# Запуск: docker build -f webui/Dockerfile -t dcap/webui:3.5.0 .
# Контекст: webui/ (содержит requirements.txt, main.py, templates, static).

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
ENV PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages:/app

# Код WebUI (пакет webui.* копируется в /app/webui)
COPY . /app/webui

RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/data /app/logs \
    && chown -R dcap:dcap /app

USER dcap

ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Healthcheck (WebUI отдаёт /health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

EXPOSE 8001

CMD ["uvicorn", "webui.main:app", "--host", "0.0.0.0", "--port", "8001"]