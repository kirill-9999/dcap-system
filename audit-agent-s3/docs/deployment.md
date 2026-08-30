# Развертывание S3-агента

## Docker

```bash
# Сборка
docker build -t dcap-s3-agent .

# Запуск
docker run -d \
  --name dcap-s3-agent \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -e S3_BUCKET=my-logs \
  -e S3_ACCESS_KEY=xxx \
  -e S3_SECRET_KEY=xxx \
  dcap-s3-agent
```

## Docker Compose

Отдельный сервис S3-агента:

```bash
# Запуск
docker compose -f docker-compose.s3.yml up -d

# Логи
docker compose -f docker-compose.s3.yml logs -f s3-agent

# Остановка
docker compose -f docker-compose.s3.yml down
```

```yaml
# docker-compose.s3.yml
services:
  s3-agent:
    build: ./audit-agent-s3
    environment:
      S3_BUCKET: my-logs
      S3_ACCESS_KEY: ${S3_ACCESS_KEY}
      S3_SECRET_KEY: ${S3_SECRET_KEY}
      MANAGER_URL: http://manager:8000
    volumes:
      - ./audit-agent-s3/config:/app/config
      - s3_data:/app/data
      - s3_logs:/app/logs
    restart: unless-stopped
```

> Сетевые алиасы `manager`/`webui` работают, если указать `MANAGER_URL` как
> имя сервиса внутри общей сети (`dcap-network`).

## Несколько бакетов

Запустите несколько экземпляров с разными переменными:

```bash
docker run -d --name s3-agent-prod -e S3_BUCKET=logs-prod -e S3_AGENT_NAME=s3-prod ...
docker run -d --name s3-agent-staging -e S3_BUCKET=logs-staging -e S3_AGENT_NAME=s3-staging ...
```

## Мониторинг в production

- **Логи** — централизованный сбор (ELK / Loki)
- **Метрики** — Prometheus (экспортер в разработке)
- **Алерты** — при падении агента / переполнении буфера
