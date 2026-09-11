# Отчёт: День 39 — Мониторинг (heartbeat-тред, Prometheus, Grafana, Alertmanager) — v3.7.0

**Дата:** 11.09.2026
**ТЗ:** `prompts/tz/day_39_monitoring.md`
**Роль:** Кодер
**Версия:** v3.7.0 (предыдущая v3.6.2)
**Ветка:** `feature/day_39_monitoring`

---

## Резюме

**Часть 1 (heartbeat-тред, BACKLOG-037/038).** Сканер во время длительного
задания (например, 22 500 файлов ~1.5 часа) не успевал слать heartbeat в
основном цикле — Manager помечал его `inactive`. Решено выделенным daemon-
потоком `scanner/src/heartbeat.py` (interval 30 c, fail-open): отправляет
`POST /api/scanner/heartbeat` со статусом `busy`/`idle`, ID текущего задания и
прогрессом независимо от основного цикла сканирования. `_mark_stale_scanners`
в Manager больше не помечает `inactive` сканеры с активным заданием
(`status='assigned'`). Плюс live-прогресс: в `scan_tasks` добавлена колонка
`progress` (JSON: files_scanned/total/percent, Alembic-миграция `002`),
сканер читает свой `state.json` фоновым `ProgressPoller` (каждые 15 c) и шлёт
прогресс в heartbeat.

**Часть 2 (Prometheus).**
- **Manager** (`GET /metrics`): HTTP-метрики через `MetricsMiddleware`,
  бизнес-метрики задач/findings (инкремент из `api/scanner.py`), gauges
  сканеров (активность, возраст heartbeat — лениво из БД при scrape),
  размер очередей Celery (LLEN Redis, fail-open). В `RedisClient` добавлен
  метод `llen()`.
- **Scanner** (`:9101`, на хосте): файлы/находки/длительность/ошибки.
- **Агенты**: linux `:9102` (`dcap_linux_*`), s3 `:9103` (`dcap_s3_*`).
- **Экспортеры** в compose: celery (:9808), postgres (:9187), redis (:9121).

**Часть 3 (Grafana).** `monitoring/grafana/provisioning/` +
2 дашборда (`dcap-overview.json`, `dcap-scanner.json`), datasource
`prometheus`.

**Часть 4 (Alertmanager).** `monitoring/alertmanager/alertmanager.yml` +
правила `monitoring/prometheus/alerts.yml` (ScannerInactive, TaskFailed,
HighErrorRate, CeleryQueueBacklog).

**Часть 5 (docs/scripts).** `docs/monitoring.md`, `scripts/monitoring-status.sh`
(+`-q`), обновлён `scripts/status.sh`, `docs/deployment.md`, `README.md`.

**Часть 6 (project_plan.md).** Статусы дня 38/39 `✅`, статистика v3.0.0,
BACKLOG-021/037/038 закрыты.

---

## Ключевые решения (адаптации ТЗ)

1. **Endpoint heartbeat.** ТЗ предлагал `POST /api/scanner/{id}/heartbeat`.
   Существующий endpoint Manager — `POST /api/scanner/heartbeat`, где
   `scanner_id` передаётся в теле. Чтобы не плодить несогласованность с
   `ManagerClient` (уже использует универсальный heartbeat), поток шлёт
   **на существующий endpoint** с `scanner_id` в теле JSON. Функционально
   эквивалентно, отклонение зафиксировано.
2. **Путь metrics у linux-агента.** ТЗ говорил `audit-agent-linux/src/metrics.py`,
   но модули linux-агента лежат в корне пакета (`main.py`, `collector.py`, …)
   с топ-уровневыми импортами — `metrics.py` размещён рядом, в корне
   `audit-agent-linux/`.
3. **S3 buffer.** `BufferManager` не имеет `count_unsent()` — размер буфера
   берётся из `get_stats().get("pending", 0)`.
4. **Celery queue size.** У `RedisClient` не было публичного доступа к
   клиенту — добавлен метод `llen(queue)` (fail-open, возвращает -1).
5. **Порты экспортеров** вынесены в `.env.example`
   (`PROMETHEUS_PORT`/`GRAFANA_PORT`/`ALERTMANAGER_PORT`/`*_EXPORTER_PORT`),
   но в docker-compose дефолты захардкожены (как и существующие сервисы) —
   переменные объявлены комментариями. `GRAFANA_PASSWORD` добавлен в `.env.example`.
6. **`import threading`** — добавлен в `managed_scanner.py`: `ProgressPoller`
   использует `threading.Thread`, но импорта не было (возможный NameError).

---

## Выполненная работа

### NEW

- `scanner/src/heartbeat.py` — `HeartbeatThread` (daemon, interval 30 c,
  fail-open; `set_task`/`set_progress`; payload `{scanner_id, status,
  current_task_id, progress:{files_scanned,total}}`).
- `scanner/src/metrics.py` — экспортер :9101 (`dcap_scanner_files_scanned_total`,
  `dcap_scanner_findings_total`[type], `dcap_scanner_file_duration_seconds`,
  `dcap_scanner_errors_total`[error_type], `dcap_scanner_current_task`),
  `start_metrics_server` (idempotent, fail-open), `set_current_task`/`clear_current_task`.
- `manager/src/metrics.py` — HTTP-метрики (`dcap_http_requests_total`,
  `dcap_http_request_duration_seconds`) + бизнес (`dcap_scanner_active`,
  `dcap_scanner_heartbeat_age_seconds`, `dcap_tasks_total`[status],
  `dcap_task_duration_seconds`, `dcap_findings_total`[type],
  `dcap_celery_queue_size`[queue]) + `MetricsMiddleware` + `metrics_endpoint()`
  (ленивое обновление gauges из БД/Redis при scrape, fail-open).
- `audit-agent-s3/src/metrics.py` — :9103 (`dcap_s3_events_collected_total`,
  `dcap_s3_events_sent_total`, `dcap_s3_send_errors_total`, `dcap_s3_buffer_size`).
- `audit-agent-linux/metrics.py` — :9102 (`dcap_linux_events_collected_total`,
  `dcap_linux_events_sent_total`, `dcap_linux_send_errors_total`, `dcap_linux_buffer_size`).
- `manager/src/db/migrations/versions/002_scanner_progress.py` — колонка
  `scan_tasks.progress` (JSON) для PostgreSQL и SQLite.
- `monitoring/prometheus/prometheus.yml` (jobs: manager:8000,
  host.docker.internal:9101, audit_agent_linux:9102, s3_agent:9103,
  celery_exporter:9808, postgres_exporter:9187, redis_exporter:9121),
  `monitoring/prometheus/alerts.yml`, `monitoring/alertmanager/alertmanager.yml`.
- `monitoring/grafana/provisioning/datasources/prometheus.yml`,
  `monitoring/grafana/provisioning/dashboards/dashboards.yml`,
  `monitoring/grafana/provisioning/dashboards/dcap-overview.json`,
  `monitoring/grafana/provisioning/dashboards/dcap-scanner.json`.
- `docs/monitoring.md`.
- `scripts/monitoring-status.sh` (+`-q`).
- `prompts/reports/day_39_report.md` (этот файл).

### Modified

- `scanner/src/managed_scanner.py` — `import threading`; `ProgressPoller`
  (читает `state.json`, interval 15 c); `_update_metrics`; в `_execute_task`
  set_task/set_progress/poller, обновление метрик в success/exception/finally;
  старт `start_metrics_server(:9101)` и `HeartbeatThread` в `run_loop`;
  остановка потока при shutdown.
- `manager/src/main.py` — `version="3.7.0"` (FastAPI title + `/api/health`),
  `MetricsMiddleware`, `GET /metrics` (публичный, вне `/api/*`).
- `manager/src/api/scanner.py` — модели `HeartbeatProgress`/`HeartbeatRequest`
  (+`task_id`, `progress`); heartbeat обновляет `Task.progress` (percent +
  `started_at`, только для `status='assigned'`); `_mark_stale_scanners` не
  трогает сканеры с активным заданием; `track_task_submitted("assigned")` в
  назначении, `track_task_submitted("completed")`/`track_task_completed`/
  `track_findings` в submit_results.
- `manager/src/db/models.py` — `ScanTask.progress = Column(JSON, nullable=True)`.
- `manager/src/cache/redis_client.py` — метод `llen(queue)`.
- `audit-agent-s3/src/main.py` — старт метрик (:9103), инкременты collected/
  sent/errors, `set_buffer_size(get_stats().get("pending", 0))`, shutdown.
- `audit-agent-linux/main.py` — старт метрик (:9102, `metrics_port` из конфига),
  инкременты collected/sent/errors, `set_buffer_size(buffer.count_unsent())`; +`main.py` настройка `metrics_port` дефолт.
- `audit-agent-linux/Dockerfile` — копирование `metrics.py`.
- `requirements.txt` (корень), `scanner/requirements.txt`,
  `audit-agent-s3/requirements.txt`, `audit-agent-linux/requirements.txt` —
  добавлен `prometheus-client>=0.20.0`.
- `docker-compose.yml` — сервисы: `prometheus` (:9090) с
  `extra_hosts: host.docker.internal:host-gateway`, `grafana` (:3000,
  `GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}`), `alertmanager`
  (:9093), `postgres_exporter`, `redis_exporter`, `celery_exporter`;
  `audit_agent_linux` (profile `agents`); volumes `prometheus_data`/`grafana_data`.
- `docker-compose.prod.yml` — ресурсные лимиты для prometheus/grafana/
  alertmanager/exporters/агентов.
- `.env.example` — порты мониторинга, `GRAFANA_PASSWORD`, `ALERTMANAGER_ENABLED`.
- `scripts/status.sh` — секция Monitoring (Prometheus/Grafana/Alertmanager/экспортеры).
- `docs/deployment.md` — раздел «Мониторинг».
- `README.md`, `AGENTS.md` — v3.7.0, релиз дня 39, структура.
- `project_plan.md` — статусы дня 38/39 `✅`, статистика v3.0.0 (14/16),
  итого 41/64 (64%), BACKLOG-021 закрыт.

---

## Тестирование

- `python -m py_compile` всех изменённых файлов (scanner/manager/агенты/миграция) — ✅
- Проверено наличие API: `manager/src/db/session.SessionLocal` ✅,
  `manager/src/cache/redis_client.get_redis` ✅ (защита от ложно-положительного)
- **Alembic**: `alembic upgrade head` на SQLite (dev-БД) — `001` (пусто для
  SQLite) + `002` (колонка `progress`) применены ✅; `scan_tasks.progress`
  присутствует, `alembic_version` = `002_scanner_progress` ✅
- `docker compose config --quiet` — ✅ base / ✅ prod / ✅ agents

---

## Запуск (ручное тестирование)

```powershell
# 1. Стек + мониторинг (Docker)
docker compose up -d            # + prometheus grafana alertmanager exporters

# 2. Сканер на хосте (метрики :9101 + heartbeat-тред)
pip install -r scanner/requirements.txt
$env:PYTHONUTF8=1
python run_scanner.py scanner/config/scanner_config.json

# 3. Проверка метрик
curl http://localhost:8000/metrics      # Manager: tasks/findings/http/celery
curl http://localhost:9101/metrics      # Scanner: files/findings/duration/errors
curl http://localhost:9090/targets      # Prometheus targets (вниз — если не up)
curl http://localhost:3000              # Grafana (admin / admin, дашборды DCAP)

# 4. Статус мониторинга
./scripts/status.sh
./scripts/monitoring-status.sh
./scripts/monitoring-status.sh -q

# 5. Heartbeat/прогресс: во время длинного задания открыть
#    GET http://localhost:8000/api/tasks/<id> — поле progress (files_scanned/total/percent)
```

Ожидаемый результат: во время длинного сканирования сканер НЕ помечается
`inactive` (heartbeat-тред), у задания заполняется `progress`, метрики и
дашборды Grafana отображают активность.

---

## Команда коммита

```powershell
# Сначала создаём ветку дня 39
git checkout -b feature/day_39_monitoring

# затем добавить изменения
git add -A
git commit -m "feat: День 39 — Мониторинг Prometheus/Grafana + heartbeat-тред (v3.7.0)

Heartbeat-тред (BACKLOG-037/038):
- scanner/src/heartbeat.py: выделенный поток (30 c, fail-open) шлёт
  POST /api/scanner/heartbeat с заданием и прогрессом — сканер не
  помечается inactive при длинных заданиях
- manager: _mark_stale_scanners не трогает сканеры с заданиями assigned
- scan_tasks.progress (JSON) + Alembic 002, обновление из heartbeat
- scanner: ProgressPoller по state.json (15 c), live-прогресс

Метрики:
- manager/src/metrics.py: HTTP/tasks/findings/scanner gauges/celery queues
  + MetricsMiddleware + GET /metrics; RedisClient.llen()
- scanner/src/metrics.py: экспортер :9101
- агенты: audit-agent-linux/metrics.py (:9102), audit-agent-s3/src/metrics.py (:9103)
- exportторы celery/postgres/redis в compose; prometheus-client в requirements

Стек мониторинга:
- monitoring/prometheus/{prometheus,alerts}.yml
- monitoring/alertmanager/alertmanager.yml
- monitoring/grafana/provisioning/ + дашборды dcap-overview, dcap-scanner
- docker-compose(+prod): prometheus/grafana/alertmanager/exporters + лимиты,
  audit_agent_linux в compose; .env.example обновлён
- docs/monitoring.md, scripts/monitoring-status.sh, status.sh
- README/AGENTS/project_plan updated (v3.7.0, BACKLOG-021/037/038 done)"
```

---

## Обратная связь архитектору

- **Endpoint heartbeat отличался от ТЗ**: использован существующий
  `/api/scanner/heartbeat` с `scanner_id` в теле (ТЗ предлагал
  `/api/scanner/{id}/heartbeat`) — иначе дублирование с `ManagerClient`.
- **Отклонение пути metrics у linux-агента** (`audit-agent-linux/metrics.py`,
  не `src/`) — модули агента лежат в корне пакета.
- **Рекомендации**: при длинных заданиях Manager не помечает сканер inactive,
  но «живой» прогресс виден только в `progress` задания — имеет смысл вынести
  прогресс в WebUI (панель «Сканеры»). Также: метрики `/metrics` сейчас
  публичные (вне `/api/*`) — при production стоит рассмотреть JWT/Внутренние
  токены для scrape (basic_auth в prometheus.yml + `authorization` в
  scrape_configs).
- **Порты экспортеров** захардкожены в compose (как и остальные порты стека);
  `.env.example` содержит переменные для будущей параметризации.