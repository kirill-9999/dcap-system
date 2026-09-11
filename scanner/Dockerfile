# scanner/Dockerfile (День 38.5) — Scanner (Tesseract + spaCy + Presidio)
# ===== STAGE 1: Builder =====
FROM python:3.11-slim AS builder

WORKDIR /build

# Системные зависимости для сборки Python-пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY scanner/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/opt/dcapdeps -r requirements.txt

# Загрузка spaCy моделей в /opt/dcapdeps.
# Код pii_classifier.py жёстко использует модели *_sm (не lg), поэтому качаем sm
# (совместимы со spacy 3.8; URL публикуются в explosion/spacy-models).
RUN pip install --no-cache-dir --prefix=/opt/dcapdeps \
        "https://github.com/explosion/spacy-models/releases/download/ru_core_news_sm-3.8.0/ru_core_news_sm-3.8.0.tar.gz" \
        "https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0.tar.gz"

# ===== STAGE 2: Runtime =====
FROM python:3.11-slim

WORKDIR /app

# Runtime зависимости: Tesseract + языки + OpenCV-зависимости + procps (для pgrep)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libxml2 \
    libxslt1.1 \
    procps \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копирование Python-пакетов из builder
COPY --from=builder /opt/dcapdeps /opt/dcapdeps
ENV PYTHONPATH=/opt/dcapdeps/lib/python3.11/site-packages:$PYTHONPATH
ENV PATH=/opt/dcapdeps/bin:$PATH

# Копирование кода (весь пакет scanner/ — смешанные импорты scanner.* и core.*)
COPY scanner/ ./scanner/
COPY run_scanner.py .

# Создание пользователя и runtime-каталогов
RUN groupadd -r dcap && useradd -r -g dcap dcap \
    && mkdir -p /app/scanner/state /app/scanner/data /app/logs /scanned \
    && chown -R dcap:dcap /app /scanned

USER dcap

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO
ENV MANAGER_URL=http://manager:8000

# Healthcheck (проверка процесса)
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=5 \
    CMD pgrep -f "run_scanner.py" || exit 1

# Сканируемые папки монтируются сюда
VOLUME ["/scanned"]

CMD ["python", "run_scanner.py", "scanner/config/scanner_config.json"]