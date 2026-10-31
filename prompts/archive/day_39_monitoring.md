📋 ТЗ: День 39 — Мониторинг (Prometheus/Grafana) + Heartbeat-thread
Дата: 11.09.2026
Роль: Кодер
Версия (целевая): v3.7.0
Ветка: feature/day_39_monitoring
Предыдущая версия: v3.6.2 (Scanner на хосте)

🎯 Цель дня
Heartbeat-thread для сканера — устранить проблему «inactive при долгом задании» (BACKLOG-037, 038)

Мониторинг — Prometheus + Grafana, метрики для Manager / Scanner / Celery / агентов

Alertmanager — алерты на ключевые события (сканер offline, ошибки, latency)

📦 Часть 1. Heartbeat-thread (BACKLOG-037, BACKLOG-038)
1.1. Проблема
Во время длительного задания (например, 22 500 файлов ~1.5 часа) сканер не шлёт heartbeat → Manager помечает его inactive, хотя сканер активно работает. Возможны ложные алерты, выдача заданий «мёртвому» сканеру, невозможность отличить «завис» от «работает долго».

1.2. Решение
Выделенный daemon-поток, который шлёт heartbeat независимо от основного цикла сканирования.

1.3. Реализация
NEW: scanner/src/heartbeat.py

python
import threading
import time
import logging
import requests

logger = logging.getLogger(__name__)

class HeartbeatThread(threading.Thread):
    """
    Выделенный поток heartbeat. Шлёт /api/scanner/{id}/heartbeat
    независимо от основного цикла сканирования.
    """
    def __init__(self, manager_url: str, scanner_id: int, interval: int = 30):
        super().__init__(daemon=True, name="HeartbeatThread")
        self.manager_url = manager_url.rstrip("/")
        self.scanner_id = scanner_id
        self.interval = interval
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._current_task_id = None
        self._current_progress = None  # {"files_scanned": int, "total": int|None}

    def set_task(self, task_id: int | None):
        with self._lock:
            self._current_task_id = task_id

    def set_progress(self, files_scanned: int, total: int | None = None):
        with self._lock:
            self._current_progress = {
                "files_scanned": files_scanned,
                "total": total,
            }

    def _build_payload(self) -> dict:
        with self._lock:
            payload = {"task_id": self._current_task_id}
            if self._current_progress:
                payload["progress"] = self._current_progress
            return payload

    def run(self):
        logger.info("HeartbeatThread started (interval=%ss)", self.interval)
        while not self._stop.wait(self.interval):
            try:
                requests.post(
                    f"{self.manager_url}/api/scanner/{self.scanner_id}/heartbeat",
                    json=self._build_payload(),
                    timeout=5,
                )
            except Exception as e:
                logger.warning("Heartbeat failed: %s", e)  # fail-open
        logger.info("HeartbeatThread stopped")

    def stop(self):
        self._stop.set()
MODIFIED: scanner/src/managed_scanner.py

При старте: создать и запустить HeartbeatThread(manager_url, scanner_id, interval=30)

При взятии задания: heartbeat_thread.set_task(task_id)

В цикле сканирования (каждые N файлов): heartbeat_thread.set_progress(files_scanned, total)

При завершении задания: heartbeat_thread.set_task(None), set_progress(0)

При остановке сканера: heartbeat_thread.stop()

MODIFIED: manager/src/api/scanner.py

POST /api/scanner/{id}/heartbeat — принимать опциональные task_id и progress

Обновлять last_heartbeat (как сейчас)

Если передан task_id — обновлять Task.progress (JSON: files_scanned, total, percent)

НЕ помечать сканер inactive, если у него есть активное задание и свежий heartbeat

MODIFIED: модель Task (если нет поля progress)

Добавить progress = Column(JSON, nullable=True) (или использовать существующее)

Alembic-миграция

1.4. Критерии приёмки (Часть 1)
□ Во время сканирования 22 500 файлов сканер остаётся active в Manager
□ Task.progress обновляется (видны files_scanned, percent)
□ При падении heartbeat-потока сканер не крашится (fail-open)
□ При завершении задания heartbeat продолжает слаться
□ python -m py_compile для изменённых файлов — ✅
□ Alembic-миграция применяется без ошибок
📊 Часть 2. Prometheus (метрики)
2.1. Экспортеры
NEW: manager/src/metrics.py

python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# HTTP
http_requests_total = Counter(
    "dcap_http_requests_total", "Total HTTP requests",
    ["method", "endpoint", "status"]
)
http_request_duration = Histogram(
    "dcap_http_request_duration_seconds", "HTTP request duration",
    ["method", "endpoint"]
)

# Бизнес-метрики
scanner_active = Gauge("dcap_scanner_active", "Active scanners", ["scanner_id"])
scanner_heartbeat_age = Gauge("dcap_scanner_heartbeat_age_seconds", "Seconds since last heartbeat", ["scanner_id"])
task_total = Counter("dcap_tasks_total", "Total tasks", ["status"])
task_duration = Histogram("dcap_task_duration_seconds", "Task duration")
findings_total = Counter("dcap_findings_total", "Total findings", ["type"])
celery_queue_size = Gauge("dcap_celery_queue_size", "Celery queue size", ["queue"])

def metrics_endpoint():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
MODIFIED: manager/src/main.py

GET /metrics → metrics_endpoint()

Middleware для http_requests_total / http_request_duration

NEW: scanner/src/metrics.py

python
from prometheus_client import Counter, Gauge, Histogram, start_http_server

files_scanned = Counter("dcap_scanner_files_scanned_total", "Files scanned", ["scanner_id"])
findings = Counter("dcap_scanner_findings_total", "Findings", ["scanner_id", "type"])
scan_duration = Histogram("dcap_scanner_file_duration_seconds", "Per-file scan duration", ["scanner_id"])
scan_errors = Counter("dcap_scanner_errors_total", "Scan errors", ["scanner_id", "error_type"])
current_task = Gauge("dcap_scanner_current_task", "Current task id", ["scanner_id"])
MODIFIED: scanner/src/managed_scanner.py

start_http_server(9101) — метрики сканера на :9101

Инкрементить files_scanned, findings, scan_errors в цикле

NEW: audit-agent-linux/src/metrics.py и audit-agent-s3/src/metrics.py

Аналогично, порт 9102/9103

Метрики: events_collected_total, events_sent_total, send_errors_total, buffer_size

Celery: используем celery-prometheus-exporter (или flower + prometheus-exporter)

В docker-compose.yml добавить сервис celery-exporter (порт 9808)

2.2. Prometheus конфигурация
NEW: monitoring/prometheus/prometheus.yml

yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alerts.yml

scrape_configs:
  - job_name: 'manager'
    static_configs:
      - targets: ['manager:8000']
    metrics_path: '/metrics'

  - job_name: 'scanner'
    static_configs:
      - targets: ['host.docker.internal:9101']
    # ВАЖНО: сканер на хосте (v3.6.2) — host.docker.internal

  - job_name: 'linux-agent'
    static_configs:
      - targets: ['audit_agent_linux:9102']

  - job_name: 's3-agent'
    static_configs:
      - targets: ['s3_agent:9103']

  - job_name: 'celery'
    static_configs:
      - targets: ['celery_exporter:9808']

  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres_exporter:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['redis_exporter:9121']
NEW: monitoring/prometheus/alerts.yml

yaml
groups:
  - name: dcap
    rules:
      - alert: ScannerInactive
        expr: dcap_scanner_heartbeat_age_seconds > 120
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "Scanner {{ $labels.scanner_id }} inactive"

      - alert: TaskFailed
        expr: increase(dcap_tasks_total{status="failed"}[5m]) > 0
        labels:
          severity: critical

      - alert: HighErrorRate
        expr: rate(dcap_http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: critical

      - alert: CeleryQueueBacklog
        expr: dcap_celery_queue_size > 100
        for: 10m
        labels:
          severity: warning
2.3. docker-compose
MODIFIED: docker-compose.yml — добавить сервисы:

yaml
  prometheus:
    image: prom/prometheus:latest
    container_name: dcap-prometheus
    volumes:
      - ./monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./monitoring/prometheus/alerts.yml:/etc/prometheus/alerts.yml:ro
      - prometheus_data:/prometheus
    ports: ["9090:9090"]
    networks: [dcap-network]
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: dcap-grafana
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:-admin}
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning:/etc/grafana/provisioning:ro
    ports: ["3000:3000"]
    depends_on: [prometheus]
    networks: [dcap-network]
    restart: unless-stopped

  alertmanager:
    image: prom/alertmanager:latest
    container_name: dcap-alertmanager
    volumes:
      - ./monitoring/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
    ports: ["9093:9093"]
    networks: [dcap-network]
    restart: unless-stopped

  postgres_exporter:
    image: prometheuscommunity/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://${POSTGRES_USER:-dcap}:${POSTGRES_PASSWORD:-dcap_password}@postgres:5432/${POSTGRES_DB:-dcap}?sslmode=disable"
    ports: ["9187:9187"]
    depends_on:
      postgres: { condition: service_healthy }
    networks: [dcap-network]

  redis_exporter:
    image: oliver006/redis_exporter:latest
    environment:
      REDIS_ADDR: "redis://redis:6379"
      REDIS_PASSWORD: ${REDIS_PASSWORD:-redis_password}
    ports: ["9121:9121"]
    depends_on:
      redis: { condition: service_healthy }
    networks: [dcap-network]

  celery_exporter:
    image: danihodovic/celery-exporter:latest
    environment:
      CELERY_BROKER_URL: "redis://:${REDIS_PASSWORD:-redis_password}@redis:6379/0"
    ports: ["9808:9808"]
    depends_on:
      redis: { condition: service_healthy }
    networks: [dcap-network]
MODIFIED: docker-compose.prod.yml — лимиты для новых сервисов.

MODIFIED: .env.example — GRAFANA_PASSWORD, ALERTMANAGER_*.

MODIFIED: requirements.txt (manager, scanner, агенты) — prometheus-client.

📈 Часть 3. Grafana (дашборды)
NEW: monitoring/grafana/provisioning/datasources/prometheus.yml

yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    isDefault: true
NEW: monitoring/grafana/provisioning/dashboards/dashboards.yml

yaml
apiVersion: 1
providers:
  - name: 'dcap'
    folder: 'DCAP'
    type: file
    options:
      path: /etc/grafana/provisioning/dashboards
NEW: monitoring/grafana/provisioning/dashboards/dcap-overview.json (dashboard-as-code)
Панели:

Scanners — active count, heartbeat age (таблица по scanner_id)

Tasks — rate по статусам (completed/failed/running), duration p50/p95/p99

Findings — rate по типам (PII / Credentials / Code)

HTTP — RPS, error rate, latency p95

Celery — queue size, task rate

Infrastructure — PostgreSQL connections, Redis memory, CPU/RAM контейнеров

NEW: monitoring/grafana/provisioning/dashboards/dcap-scanner.json — детальный дашборд сканера (files/sec, OCR latency, errors by type).

🔔 Часть 4. Alertmanager
NEW: monitoring/alertmanager/alertmanager.yml

yaml
route:
  receiver: 'default'
  group_by: ['alertname', 'severity']
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 1h

receivers:
  - name: 'default'
    webhook_configs:
      - url: 'http://manager:8000/api/alerts/webhook'  # опционально
        send_resolved: true
Опционально — email/Slack/Telegram (через env).

📁 Часть 5. Документация и скрипты
NEW: docs/monitoring.md

Архитектура мониторинга

Как открыть: Grafana :3000 (admin/${GRAFANA_PASSWORD}), Prometheus :9090, Alertmanager :9093

Список метрик

Список алертов

Как добавить свою метрику/дашборд/алерт

Troubleshooting (targets down, host.docker.internal на Linux)

MODIFIED: docs/deployment.md — раздел «Мониторинг» + ссылка на monitoring.md.

MODIFIED: scripts/status.sh — добавить проверку Prometheus/Grafana/Alertmanager.

NEW: scripts/monitoring-status.sh — проверка targets Prometheus, health Grafana, алертов.

🗂️ Часть 6. Бэклог (добавить в project_plan.md)
ID	Название	Версия	Приоритет	Источник
BACKLOG-037	Heartbeat-thread для сканера	v3.0.0	🔴	День 38.5
BACKLOG-038	Прогресс-пинг в heartbeat (task_id + progress)	v3.0.0	🟡	День 38.5
BACKLOG-039	Аудит других NOT NULL полей в приёмных эндпоинтах	v3.0.0	🟡	День 38.5
BACKLOG-040	Параллельный батч-сканер (несколько процессов)	v3.1.0	🟡	День 38.5
BACKLOG-041	Prometheus/Grafana мониторинг	v3.0.0	🔴	День 39
BACKLOG-042	Alertmanager + алерты	v3.0.0	🟡	День 39
🧪 Тестирование
Heartbeat
□ python -m py_compile scanner/src/heartbeat.py scanner/src/managed_scanner.py manager/src/api/scanner.py — ✅
□ Alembic upgrade head — ✅
□ E2E: запустить сканер на хосте, взять задание, убедиться, что scanner.status = active всё время сканирования
□ Проверить Task.progress в БД — обновляется
□ Убить heartbeat-поток (kill -9) — сканер не крашится
□ После завершения задания heartbeat продолжает слаться
Мониторинг
□ docker compose config -q — ✅ (base + prod + agents)
□ Все образы собираются (docker compose build prometheus grafana alertmanager postgres_exporter redis_exporter celery_exporter)
□ docker compose up -d → все контейнеры healthy
□ Prometheus /targets — все targets UP (manager, scanner, celery, postgres, redis, агенты)
□ Grafana: дашборды DCAP Overview и DCAP Scanner видны, панели заполняются
□ Alertmanager: ScannerInactive срабатывает при остановке сканера
□ curl http://localhost:8000/metrics — метрики Manager отдаются
□ curl http://host.docker.internal:9101/metrics — метрики сканера отдаются
📦 Артефакты (итог)
NEW:

scanner/src/heartbeat.py

scanner/src/metrics.py

manager/src/metrics.py

audit-agent-linux/src/metrics.py

audit-agent-s3/src/metrics.py

monitoring/prometheus/prometheus.yml

monitoring/prometheus/alerts.yml

monitoring/alertmanager/alertmanager.yml

monitoring/grafana/provisioning/datasources/prometheus.yml

monitoring/grafana/provisioning/dashboards/dashboards.yml

monitoring/grafana/provisioning/dashboards/dcap-overview.json

monitoring/grafana/provisioning/dashboards/dcap-scanner.json

docs/monitoring.md

scripts/monitoring-status.sh

prompts/reports/day_39_report.md (после выполнения)

MODIFIED:

scanner/src/managed_scanner.py (heartbeat-thread + metrics)

manager/src/api/scanner.py (heartbeat с task_id/progress)

manager/src/main.py (/metrics + middleware)

manager/src/db/models.py (Task.progress)

audit-agent-linux/src/main.py (metrics server)

audit-agent-s3/src/main.py (metrics server)

docker-compose.yml (prometheus, grafana, alertmanager, exporters)

docker-compose.prod.yml (лимиты для новых)

.env.example (GRAFANA_PASSWORD и др.)

requirements.txt (manager, scanner, агенты) — prometheus-client

scripts/status.sh (проверка monitoring)

docs/deployment.md (раздел мониторинг)

README.md, AGENTS.md, project_plan.md, project_context.md

DELETED: —

✅ Критерии приёмки Дня 39
Heartbeat-thread работает: сканер остаётся active во время долгого задания, Task.progress обновляется

Prometheus собирает метрики со всех компонентов (manager, scanner, агенты, celery, postgres, redis)

Grafana — 2 дашборда (Overview, Scanner), панели заполняются

Alertmanager — алерт ScannerInactive срабатывает

Docker-compose — up -d поднимает весь стек без ошибок, все healthy

Документация — docs/monitoring.md, обновлён deployment.md

Тесты — все пункты из раздела «Тестирование» пройдены

🚀 Команда коммита (после выполнения)
bash
git checkout -b feature/day_39_monitoring
git add .
git commit -m "feat: День 39 — Мониторинг (Prometheus/Grafana) + Heartbeat-thread

Heartbeat-thread (BACKLOG-037, 038):
- scanner/src/heartbeat.py — выделенный daemon-поток heartbeat
- managed_scanner.py: set_task/set_progress, fail-open, stop
- manager/src/api/scanner.py: heartbeat принимает task_id + progress
- Task.progress (JSON) + Alembic-миграция

Мониторинг (BACKLOG-041, 042):
- manager/src/metrics.py (HTTP, tasks, findings, scanner)
- scanner/src/metrics.py (files, findings, errors) :9101
- agent metrics :9102 / :9103
- monitoring/prometheus/{prometheus,alerts}.yml
- monitoring/alertmanager/alertmanager.yml
- monitoring/grafana/provisioning/... (2 дашборда)
- docker-compose: prometheus, grafana, alertmanager, exporters
- docs/monitoring.md, scripts/monitoring-status.sh

Проверено: сканер active во время долгого задания, targets UP,
дашборды заполняются, алерт ScannerInactive срабатывает."
📝 Обратная связь архитектору (шаблон)
После выполнения — заполнить:

Что заработало / что нет

Отклонения от ТЗ (если были)

Замечания по host.docker.internal на Linux (может понадобиться extra_hosts)

Производительность экспортеров

Готовность к Дню 40-41 (E2E + Chaos)