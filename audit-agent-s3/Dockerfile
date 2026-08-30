# audit-agent-s3/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Создание директорий
RUN mkdir -p data/state data/buffer logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Точка входа
ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--config", "config/config.json"]
