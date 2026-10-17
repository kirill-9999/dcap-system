# DCAP System — Мониторинг (День 39)

Архитектура мониторинга DCAP: **Prometheus** (сбор + алерты) + **Grafana**
(дашборды) + **Alertmanager** (уведомления). Метрики собираются с Manager,
сканера (на хосте), Celery, PostgreSQL, Redis и агентов аудита.

```
                        ┌──────────────┐
   manager :8000  ─────>│  Prometheus  │<─────  Grafana :3000
   scanner :9101  ─────>│   :9090      │        Alertmanager :9093
  linux-agent :9102 ───>│              │
    s3-agent :9103 ────>│              │
   celery_exporter ────>│              │
 postgres_exporter ────>└──────────────┘
 redis_exporter
```

## Как открыть

| Сервис       | URL                      | Логин                          |
|--------------|--------------------------|--------------------------------|
| Grafana      | http://localhost:3000    | `admin` / `${GRAFANA_PASSWORD}` (по умолчанию `admin`) |
| Prometheus   | http://localhost:9090    | —                              |
| Alertmanager | http://localhost:9093    | —                              |

## Запуск

```bash
# Весь стек (Manager + WebUI + мониторинг):
docker compose up -d

# Отдельно только мониторинг (если стек уже запущен локально через run_all.py):
docker compose up -d prometheus grafana alertmanager

# S3/Linux-агенты (профиль agents):
docker compose --profile agents up -d

# Статус:
./scripts/status.sh
./scripts/monitoring-status.sh
./scripts/monitoring-status.sh -q   # только проблемы (для cron)
```

## Список метрик

### Manager (`GET /metrics` на :8000)

| Метрика | Тип | Метки | Описание |
|---------|-----|-------|----------|
| `dcap_http_requests_total` | Counter | method, endpoint, status | Все HTTP-запросы |
| `dcap_http_request_duration_seconds` | Histogram | method, endpoint | Latency HTTP |
| `dcap_scanner_active` | Gauge | scanner_id | Активен ли сканер (1/0) |
| `dcap_scanner_heartbeat_age_seconds` | Gauge | scanner_id | Секунд с последнего heartbeat |
| `dcap_tasks_total` | Counter | status | Задания по статусам |
| `dcap_task_duration_seconds` | Histogram | — | Длительность заданий |
| `dcap_findings_total` | Gauge | type | Находки в БД по типам (PII/Credentials/Code), обновляется из БД при scrape |
| `dcap_findings_created_total` | Counter | type | Находки, созданные за сессию процесса |
| `dcap_celery_queue_size` | Gauge | queue | Размер очередей Celery |

### Scanner (`:9101`, на хосте через `host.docker.internal`)

| Метрика | Тип | Описание |
|---------|-----|----------|
| `dcap_scanner_files_scanned_total` | Counter | Обработанные файлы |
| `dcap_scanner_findings_total` | Counter | Находки |
| `dcap_scanner_file_duration_seconds` | Histogram | Время обработки файла |
| `dcap_scanner_errors_total` | Counter | Ошибки по типам |
| `dcap_scanner_current_task` | Gauge | Текущее задание |

### Агенты аудита

- Linux-агент (`:9102`): `dcap_linux_events_collected_total`,
  `dcap_linux_events_sent_total`, `dcap_linux_send_errors_total`,
  `dcap_linux_buffer_size`.
- S3-агент (`:9103`): `dcap_s3_events_collected_total`,
  `dcap_s3_events_sent_total`, `dcap_s3_send_errors_total`,
  `dcap_s3_buffer_size`.

### Экспортеры (docker-compose)

- **Celery** — `celery_exporter` (danihodovic) на :9808: метрики
  `celery_tasks_total`, `celery_task_runtime_seconds` и др.
- **PostgreSQL** — `postgres_exporter` на :9187: `pg_stat_*` (в т.ч.
  `pg_stat_activity_count`).
- **Redis** — `redis_exporter` на :9121: `redis_memory_used_bytes` и др.

## Список алертов (`monitoring/prometheus/alerts.yml`)

| Алерт | Выражение | Severity |
|-------|-----------|----------|
| `ScannerInactive` | `dcap_scanner_heartbeat_age_seconds > 120` | warning |
| `TaskFailed` | `increase(dcap_tasks_total{status="failed"}[5m]) > 0` | critical |
| `HighErrorRate` | `rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05` | critical |
| `CeleryQueueBacklog` | `dcap_celery_queue_size > 100` | warning |

Уведомления настраиваются в `monitoring/alertmanager/alertmanager.yml`
(receiver `default` → webhook на Manager `/api/alerts/webhook`; email/Slack/
Telegram — по образцу в комментариях).

## Дашборды Grafana

Provisioning в `monitoring/grafana/provisioning/` (создаются автоматически):

- **DCAP / DCAP Overview** — сканеры, задания, находки, HTTP, Celery,
  инфраструктура (PostgreSQL/Redis).
- **DCAP / DCAP Scanner** — детальный дашборд сканера (files/s, OCR latency,
  ошибки по типам).

## Как добавить свою метрику

1. В `manager/src/metrics.py` (или `scanner/src/metrics.py`,
   `audit-agent-*/metrics.py`) — объявить `Counter`/`Gauge`/`Histogram`.
2. Инкрементить в соответствующем месте кода (`track_*` функции / middleware /
   в цикле).
3. В `monitoring/grafana/provisioning/dashboards/*.json` — добавить панель
   с `expr` по новой метрике (uid datasource `prometheus`).
4. В `monitoring/prometheus/alerts.yml` — при необходимости правило.

## Как добавить алерт

Правило в `monitoring/prometheus/alerts.yml` (группа `dcap`):
`expr` (PromQL), `for` (длительность до срабатывания), `labels.severity`,
`annotations.summary`. Релоад Prometheus: `docker compose restart prometheus`.

## Troubleshooting

### Targets Prometheus down

- `./scripts/monitoring-status.sh` — показать targets и их health;
  `docker compose ps` — живы ли контейнеры.
- Manager `target down` — проверьте, что `manager` контейнер отвечает на
  `/metrics` (`curl http://localhost:8000/metrics`).
- Scanner `target down` — сканер запущен на хосте? `python run_scanner.py
  scanner/config/scanner_config.json`. Если метрики не отдаются — проверьте
  порт `9101` слушается (`curl http://localhost:9101/metrics`).

### `host.docker.internal` на Linux

`host.docker.internal` доступен по умолчанию в Docker Desktop (Windows/MacOS).
На чистом Linux-хосте в `docker-compose.yml` сервиса `prometheus` уже
добавлен `extra_hosts: - "host.docker.internal:host-gateway"`, поэтому
работает из коробки. Если нет — добавьте этот параметр.

### Grafana не видит алерты / панели пустые

- Проверьте datasource Prometheus: **Configuration → Data Sources → Prometheus**
  (url `http://prometheus:9090`).
- Панели с `dcap_*` метриками пусты, пока компоненты не начали их отдавать
  (первые данные появятся через интервал scrape 15s).

### Порт 9101 уже занят

Сканер слушает `0.0.0.0:9101` (дефолт). При конфликте — поменяйте порт в
`scanner/src/managed_scanner.py` (`port=9101`) и `monitoring/prometheus/prometheus.yml`.