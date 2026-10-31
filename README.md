# DCAP System

╨б╨╕╤Б╤В╨╡╨╝╨░ ╤Б╨║╨░╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╤П ╨╕ ╨░╤Г╨┤╨╕╤В╨░ ╨┤╨░╨╜╨╜╤Л╤Е (PII/credentials/code) ╨┤╨╗╤П Windows ╨╕ Linux.

## ╨Ъ╨╛╨╝╨┐╨╛╨╜╨╡╨╜╤В╤Л

| ╨Ъ╨╛╨╝╨┐╨╛╨╜╨╡╨╜╤В | ╨Ю╨┐╨╕╤Б╨░╨╜╨╕╨╡ | ╨Я╨╛╤А╤В |
|-----------|----------|------|
| `manager/` | FastAPI control-plane | :8000 |
| `webui/` | ╨Ф╨░╤И╨▒╨╛╤А╨┤ (Jinja2, ╨┐╤А╨╛╨║╤Б╨╕ API ╨╜╨░ Manager) | :8001 |
| `scanner/` | ╨Р╨│╨╡╨╜╤В ╤Б╨║╨░╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╤П | тАФ |
| `audit-agent-windows/` | Windows-╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░ (wevtutil) | тАФ |
| `audit-agent-linux/` | Linux-╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░ (watchdog) | тАФ |
| `audit-agent-s3/` | S3/MinIO ╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░ (polling) | тАФ |
| `shared/` | ╨Х╨┤╨╕╨╜╨░╤П ╤Б╤Е╨╡╨╝╨░ ╤Б╨╛╨▒╤Л╤В╨╕╨╣ (UnifiedEvent) | тАФ |

## ╨Ч╨░╨┐╤Г╤Б╨║

```bash
# ╨Ш╨╜╨╕╤Ж╨╕╨░╨╗╨╕╨╖╨░╤Ж╨╕╤П ╨С╨Ф
python init_db.py

# ╨Х╨┤╨╕╨╜╤Л╨╣ ╨╖╨░╨┐╤Г╤Б╨║ Manager + WebUI (╨┐╨╛╤А╤В╤Л ╨╕╨╖ ╨║╨╛╨╜╤Д╨╕╨│╨╛╨▓)
python run_all.py

# ╨╕╨╗╨╕ ╨┐╨╛ ╨╛╤В╨┤╨╡╨╗╤М╨╜╨╛╤Б╤В╨╕:
python run_manager.py        # Manager API (╨┐╨╛╤А╤В ╨╕╨╖ manager/config/config.json, :8000)
python run_webui.py          # WebUI (╨┐╨╛╤А╤В ╨╕╨╖ webui/config/config.json, :8001)

# ╨б╨║╨░╨╜╨╡╤А
python run_scanner.py scanner/config/scanner_config.json

# Windows-╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░
cd audit-agent-windows && python main.py config.json

# Linux-╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░
cd audit-agent-linux && ./start.sh --daemon

# S3/MinIO ╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░
cd audit-agent-s3 && python -m src.main --config config/config.json
```

## ╨Ь╨░╤Б╤И╤В╨░╨▒╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡ (╨Ф╨╡╨╜╤М 36-37): PostgreSQL + Redis + Celery

Production-╤Б╤В╨╡╨║ ╨┐╨╛╨┤╨╜╨╕╨╝╨░╨╡╤В╤Б╤П ╨╛╨┤╨╜╨╛╨╣ ╨║╨╛╨╝╨░╨╜╨┤╨╛╨╣:

```bash
docker compose up -d     # postgres(5432) + redis(6379) + manager(8000) + webui(8001) + celery worker/beat + flower(5555)
```

- **PostgreSQL 16** тАФ ╨╛╤Б╨╜╨╛╨▓╨╜╨░╤П ╨С╨Ф (`postgres:16-alpine`). ╨Ь╨╕╨│╤А╨░╤Ж╨╕╨╕ тАФ Alembic:
  ```bash
  alembic upgrade head
  python scripts/migrate_sqlite_to_postgres.py  # ╨┐╨╡╤А╨╡╨╜╨╛╤Б ╨┤╨░╨╜╨╜╤Л╤Е ╨╕╨╖ SQLite (╨▓╤Б╨╡ ╤В╨░╨▒╨╗╨╕╤Ж╤Л + ╨░╤А╤Е╨╕╨▓╤Л)
  ```
- **╨Я╨░╤А╤В╨╕╤Ж╨╕╨╛╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡** `audit_logs` ╨┐╨╛ ╨╝╨╡╤Б╤П╤Ж╨░╨╝ (RANGE on `created_at`), ╤Б╨╛╨╖╨┤╨░╤С╤В╤Б╤П ╨╝╨╕╨│╤А╨░╤Ж╨╕╨╡╨╣ `001_initial_postgres` ╨┤╨╗╤П PostgreSQL; SQLite-╤А╨╡╨╢╨╕╨╝ ╨╜╨╡ ╨╖╨░╤В╤А╨╛╨╜╤Г╤В.
- **Redis 7** тАФ ╨▒╤А╨╛╨║╨╡╤А Celery + ╨║╤Н╤И + rate-limit. ╨Я╤А╨╕ ╨╜╨╡╨┤╨╛╤Б╤В╤Г╨┐╨╜╨╛╤Б╤В╨╕ Redis Manager ╤А╨░╨▒╨╛╤В╨░╨╡╤В ╨▓ no-op ╤А╨╡╨╢╨╕╨╝╨╡ (rate-limit fail-open ╨▓ ╨┐╨░╨╝╤П╤В╨╕).
- **Celery** тАФ ╨╛╤З╨╡╤А╨╡╨┤╨╕: `audit_events`, `scanner_tasks`, `retention`, `reports`. ╨Я╨╡╤А╨╕╨╛╨┤╨╕╤З╨╡╤Б╨║╨░╤П ╨░╤А╤Е╨╕╨▓╨░╤Ж╨╕╤П тАФ Celery Beat (╨╖╨░╨╝╨╡╨╜╨╕╨╗╨░ ╤Д╨╛╨╜╨╛╨▓╤Л╨╣ ╨┐╨╛╤В╨╛╨║ ╨┤╨╜╤П 35).
  ```bash
  celery -A manager.src.workers.celery_app:app worker --queues=audit_events,scanner_tasks,retention,reports
  celery -A manager.src.workers.celery_app:app beat
  ```
- **Flower** тАФ ╨╝╨╛╨╜╨╕╤В╨╛╤А╨╕╨╜╨│ ╨╖╨░╨┤╨░╤З ╨╜╨░ :5555.

╨Ы╨╛╨║╨░╨╗╤М╨╜╤Л╨╣ ╨╖╨░╨┐╤Г╤Б╨║ (╨▒╨╡╨╖ Docker) ╨╛╤Б╤В╨░╤С╤В╤Б╤П ╨┐╤А╨╡╨╢╨╜╨╕╨╝: SQLite + ╨▒╨╡╨╖ RabbitMQ/Celery (╨░╤Б╨╕╨╜╤Е╤А╨╛╨╜╨╜╤Л╨╡ ╨╖╨░╨┤╨░╤З╨╕ ╨╛╨┐╤Ж╨╕╨╛╨╜╨░╨╗╤М╨╜╤Л).

## ╨Ъ╨╛╨╜╤В╨╡╨╣╨╜╨╡╤А╨╕╨╖╨░╤Ж╨╕╤П ╨╕ ╨┤╨╡╨┐╨╗╨╛╨╣ (╨Ф╨╡╨╜╤М 38)

╨Я╨╛╨╗╨╜╨░╤П ╨║╨╛╨╜╤В╨╡╨╣╨╜╨╡╤А╨╕╨╖╨░╤Ж╨╕╤П ╨▓╤Б╨╡╤Е ╨║╨╛╨╝╨┐╨╛╨╜╨╡╨╜╤В╨╛╨▓ тАФ ╨╛╨┤╨╜╨░ ╨║╨╛╨╝╨░╨╜╨┤╨░ ╨┐╨╛╨┤╨╜╨╕╨╝╨░╨╡╤В ╨▓╨╡╤Б╤М ╤Б╤В╨╡╨║.

```bash
cp .env.example .env    # ╨╜╨░╤Б╤В╤А╨╛╨╕╤В╤М ╨┐╨░╤А╨╛╨╗╨╕ ╨╕ ╨║╨╗╤О╤З╨╕
./scripts/deploy.sh     # ╤Б╨▒╨╛╤А╨║╨░ ╨╛╨▒╤А╨░╨╖╨╛╨▓ + ╨╖╨░╨┐╤Г╤Б╨║ ╨▓╤Б╨╡╤Е ╤Б╨╡╤А╨▓╨╕╤Б╨╛╨▓ + healthcheck
```

- **Dockerfile** (multi-stage, ╨╜╨╡╨┐╤А╨╕╨▓╨╕╨╗╨╡╨│╨╕╤А╨╛╨▓╨░╨╜╨╜╤Л╨╣ ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╤М, healthcheck): `manager/` (Manager + Celery worker/beat), `webui/`, `audit-agent-s3/`, `audit-agent-linux/`; `.dockerignore` ╨┤╨╗╤П ╨║╨░╨╢╨┤╨╛╨│╨╛ (build-╨║╨╛╨╜╤В╨╡╨║╤Б╤В Manager/S3 тАФ ╨║╨╛╤А╨╡╨╜╤М ╤А╨╡╨┐╨╛; webui тАФ `./webui`).
- **docker-compose.yml** тАФ ╨┐╨╛╨╗╨╜╤Л╨╣ ╤Б╤В╨╡╨║: postgres(5432) + redis(6379) + manager(8000) + webui(8001) + celery worker/beat + flower(5555). ╨Р╨│╨╡╨╜╤В╤Л тАФ profile: `--profile agents` (S3).
- **Scanner тАФ ╨Э╨Х ╨▓ Docker** (╨▓ ╨║╨╛╨╜╤В╨╡╨╣╨╜╨╡╤А╨╡ ╨╜╨╡╨╗╤М╨╖╤П ╨┤╨╕╨╜╨░╨╝╨╕╤З╨╡╤Б╨║╨╕ ╨┐╤А╨╕╨╝╨╛╨╜╤В╨╕╤А╨╛╨▓╨░╤В╤М ╨┐╨░╨┐╨║╨╕ ╨╕╨╖ ╨╖╨░╨┤╨░╨╜╨╕╨╣): ╨╖╨░╨┐╤Г╤Б╨║╨░╨╡╤В╤Б╤П ╨╜╨░ ╤Е╨╛╤Б╤В╨╡ ╤З╨╡╤А╨╡╨╖ `python run_scanner.py scanner/config/scanner_config.json` ╨╕ ╨▓╨╕╨┤╨╕╤В ╨╗╤О╨▒╤Л╨╡ ╨┐╤Г╤В╨╕ ╨╜╨░╨┐╤А╤П╨╝╤Г╤О (╤Б╨╝. `docs/deployment.md`).
- **docker-compose.prod.yml** тАФ production overrides (╨╗╨╕╨╝╨╕╤В╤Л CPU/RAM, mTLS, ╤А╨╡╨┐╨╗╨╕╨║╨░╤Ж╨╕╤П worker).
- **╨б╨║╤А╨╕╨┐╤В╤Л**: `scripts/deploy.sh`, `stop.sh`, `logs.sh`, `status.sh`, `healthcheck.sh`.
- **╨Ф╨╛╨║╤Г╨╝╨╡╨╜╤В╨░╤Ж╨╕╤П**: `docs/deployment.md`.

## ╨в╨╡╤Б╤В╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡ (╨Ф╨╡╨╜╤М 40-41): E2E + Chaos + Load

╨в╨╡╤Б╤В╤Л ╨┐╨╛╤Б╤В╤А╨╛╨╡╨╜╤Л ╨╜╨░ **pytest** (╨╕╨╖╨╛╨╗╨╕╤А╨╛╨▓╨░╨╜╨╜╤Л╨╣ ╤В╨╡╤Б╤В╨╛╨▓╤Л╨╣ ╤Б╤В╨╡╨║ `docker-compose.test.yml`,
Manager :18000, WebUI :18001, ╨С╨Ф `dcap_test`, tmpfs). ╨Я╨╛╨╗╨╜╨░╤П ╨╕╨╜╤Б╤В╤А╤Г╨║╤Ж╨╕╤П тАФ
**`docs/testing.md`**.

```bash
pip install -r requirements-dev.txt
./scripts/test-up.sh        # ╨┐╨╛╨┤╨╜╤П╤В╤М ╨╕╨╖╨╛╨╗╨╕╤А╨╛╨▓╨░╨╜╨╜╤Л╨╣ ╤В╨╡╤Б╤В╨╛╨▓╤Л╨╣ ╤Б╤В╨╡╨║
pytest tests/               # ╨▓╤Б╨╡ ╤В╨╡╤Б╤В╤Л
./scripts/run-tests.sh e2e  # ╤В╨╛╨╗╤М╨║╨╛ E2E (╨╕╨╗╨╕ chaos / load / quick / all)
./scripts/test-down.sh      # ╨╛╤Б╤В╨░╨╜╨╛╨▓╨╕╤В╤М ╤Б╤В╨╡╨║
```

- **E2E** тАФ `tests/e2e/`: ╨┐╨╛╨╗╨╜╤Л╨╣ ╤Ж╨╕╨║╨╗ (╨╖╨░╨┤╨░╨╜╨╕╨╡ тЖТ ╤Б╨║╨░╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡ тЖТ ╨╜╨░╤Е╨╛╨┤╨║╨╕), auth, heartbeat ╤Б╨║╨░╨╜╨╡╤А╨░, ╨░╨│╨╡╨╜╤В╤Л, WebUI-╨┐╤А╨╛╨║╤Б╨╕, retention
- **Chaos** тАФ `tests/chaos/`: ╨┐╨░╨┤╨╡╨╜╨╕╨╡ Manager / Redis (fail-open) / PostgreSQL / Scanner, ╨╛╨▒╤А╤Л╨▓ ╤Б╨╡╤В╨╕
- **Load** тАФ `tests/load/`: 1000 ╨╖╨░╨┤╨░╨╜╨╕╨╣, 10 000 ╤Б╨╛╨▒╤Л╤В╨╕╨╣, ╨║╨╛╨╜╨║╤Г╤А╨╡╨╜╤В╨╜╤Л╨╡ ╤Б╨║╨░╨╜╨╡╤А╤Л (╨▒╨░╨╖╨╛╨▓╤Л╨╡; ╨│╨╗╤Г╨▒╨╛╨║╨╕╨╡ тАФ ╨▓ v3.1.0)

## ╨Ь╨╛╨╜╨╕╤В╨╛╤А╨╕╨╜╨│ (╨Ф╨╡╨╜╤М 39): Prometheus + Grafana + Alertmanager

╨б╤В╨╡╨║ ╨╝╨╛╨╜╨╕╤В╨╛╤А╨╕╨╜╨│╨░ ╨┐╨╛╨┤╨╜╨╕╨╝╨░╨╡╤В╤Б╤П ╨▓╨╝╨╡╤Б╤В╨╡ ╤Б docker-compose:

```bash
docker compose up -d prometheus grafana alertmanager \
  postgres_exporter redis_exporter celery_exporter
```

- **Grafana** тАФ http://localhost:3000 (`admin` / `${GRAFANA_PASSWORD}`, ╨┤╨╡╤Д╨╛╨╗╤В `admin`); provisioning ╨┤╨░╤И╨▒╨╛╤А╨┤╨╛╨▓ ╨╕╨╖ `monitoring/grafana/provisioning/`
- **Prometheus** тАФ http://localhost:9090; ╤В╨░╤А╨│╨╡╤В╤Л ╨▓ `monitoring/prometheus/prometheus.yml`
- **Alertmanager** тАФ http://localhost:9093; ╤Г╨▓╨╡╨┤╨╛╨╝╨╗╨╡╨╜╨╕╤П (webhook/email/Slack/Telegram)
- **╨Р╨╗╨╡╤А╤В╤Л** тАФ `monitoring/prometheus/alerts.yml` (ScannerInactive, TaskFailed, HighErrorRate, CeleryQueueBacklog)
- **╨Ь╨╡╤В╤А╨╕╨║╨╕**:
  - Manager тАФ `GET /metrics` (HTTP, tasks, findings, scanner heartbeat age, celery queues)
  - Scanner (╤Е╨╛╤Б╤В, :9101) тАФ files/findings/duration/errors, ╤Б╨╛╨▒╨╕╤А╨░╨╡╤В╤Б╤П ╤З╨╡╤А╨╡╨╖ `host.docker.internal`
  - Linux-╨░╨│╨╡╨╜╤В (:9102), S3-╨░╨│╨╡╨╜╤В (:9103), ╤Н╨║╤Б╨┐╨╛╤А╤В╨╡╤А╤Л Celery/PostgreSQL/Redis
- **Heartbeat-╤В╤А╨╡╨┤ ╤Б╨║╨░╨╜╨╡╤А╨░**: ╤Д╨╛╨╜╨╛╨▓╤Л╨╣ ╨┐╨╛╤В╨╛╨║ ╤И╨╗╤С╤В heartbeat ╨║╨░╨╢╨┤╤Л╨╡ 30 ╤Б (╨▓ ╤В.╤З. ╨┐╤А╨╛╨│╤А╨╡╤Б╤Б ╨┤╨╗╨╕╨╜╨╜╤Л╤Е ╨╖╨░╨┤╨░╨╜╨╕╨╣) тАФ ╤Б╨║╨░╨╜╨╡╤А ╨▒╨╛╨╗╤М╤И╨╡ ╨╜╨╡ ╨┐╨╛╨╝╨╡╤З╨░╨╡╤В╤Б╤П "inactive" ╨▓╨╛ ╨▓╤А╨╡╨╝╤П ╤Б╨║╨░╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╤П
- **╨б╤В╨░╤В╤Г╤Б**: `./scripts/monitoring-status.sh` (╨┐╨╛╨╗╨╜╤Л╨╣) ╨╕ `-q` (╤В╨╛╨╗╤М╨║╨╛ ╨┐╤А╨╛╨▒╨╗╨╡╨╝╤Л)
- **╨Ф╨╛╨║╤Г╨╝╨╡╨╜╤В╨░╤Ж╨╕╤П**: `docs/monitoring.md`

## ╨Р╤А╤Е╨╕╤В╨╡╨║╤В╤Г╤А╨░

```
тФМтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФР     тФМтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФР     тФМтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФР
тФВ audit-agent тФВтФАтФАтФАтФАтЦ╢тФВ   Manager   тФВтЧАтФАтФАтФАтФАтФВ audit-agent тФВ
тФВ  (Windows)  тФВ     тФВ   :8000     тФВ     тФВ   (Linux)   тФВ
тФФтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФШ     тФФтФАтФАтФАтФАтФАтФАтФмтФАтФАтФАтФАтФАтФАтФШ     тФФтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФШ
                           тФВ
                    тФМтФАтФАтФАтФАтФАтФАтЦ╝тФАтФАтФАтФАтФАтФАтФР
                    тФВ    WebUI    тФВ
                    тФВ   :8001     тФВ
                    тФФтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФАтФШ
```

- **Manager** тАФ REST API, ╨┐╤А╨╕╨╡╨╝ ╤Б╨╛╨▒╤Л╤В╨╕╨╣ ╨╛╤В ╨░╨│╨╡╨╜╤В╨╛╨▓, ╤Е╤А╨░╨╜╨╡╨╜╨╕╨╡ ╨▓ PostgreSQL (╨╕╨╗╨╕ SQLite ╨▓ dev-╤А╨╡╨╢╨╕╨╝╨╡)
- **WebUI** тАФ ╨┤╨░╤И╨▒╨╛╤А╨┤ ╤Б ╤Д╨╕╨╗╤М╤В╤А╨░╤Ж╨╕╨╡╨╣ ╨┐╨╛ ╨╕╤Б╤В╨╛╤З╨╜╨╕╨║╤Г (Windows/Linux), ╤Г╨┤╨░╨╗╨╡╨╜╨╕╨╡ ╨░╨│╨╡╨╜╤В╨╛╨▓/╤Б╨║╨░╨╜╨╡╤А╨╛╨▓. ╨Т╤Б╨╡ `/api/*` ╨╖╨░╨┐╤А╨╛╤Б╤Л ╨┐╤А╨╛╨║╤Б╨╕╤А╤Г╤О╤В╤Б╤П ╨▓ Manager (╨╜╨╡╤В ╨┐╤А╤П╨╝╨╛╨│╨╛ ╨┤╨╛╤Б╤В╤Г╨┐╨░ ╨║ ╨С╨Ф)
- **╨Р╨│╨╡╨╜╤В╤Л** тАФ ╨╗╨╡╨│╨║╨╕╨╡ ╨║╨╛╨╝╨┐╨╛╨╜╨╡╨╜╤В╤Л, ╨▒╤Г╤Д╨╡╤А╨╕╨╖╤Г╤О╤В ╤Б╨╛╨▒╤Л╤В╨╕╤П ╨▓ SQLite, ╨╛╤В╨┐╤А╨░╨▓╨╗╤П╤О╤В ╨▒╨░╤В╤З╨░╨╝╨╕

## ╨Х╨┤╨╕╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В ╤Б╨╛╨▒╤Л╤В╨╕╨╣

╨Т╤Б╨╡ ╨░╨│╨╡╨╜╤В╤Л (Windows, Linux, S3, scanner) ╨╕╤Б╨┐╨╛╨╗╤М╨╖╤Г╤О╤В ╤Д╨╛╤А╨╝╨░╤В `UnifiedEvent`:

- `event_type`: read, write, delete, move, rename
- `event_source`: windows_agent, linux_agent, scanner, s3_agent
- `user`, `user_sid`, `file_path`, `source_host`, `metadata`

## ╨Т╨╡╤А╤Б╨╕╨╕

| ╨Т╨╡╤А╤Б╨╕╤П | ╨Ю╨┐╨╕╤Б╨░╨╜╨╕╨╡ |
|--------|----------|
| v1.0.0 | ╨С╨░╨╖╨╛╨▓╤Л╨╣ ╤Д╤Г╨╜╨║╤Ж╨╕╨╛╨╜╨░╨╗ (╨╛╨▒╨╜╨░╤А╤Г╨╢╨╡╨╜╨╕╨╡ + ╨║╨╗╨░╤Б╤Б╨╕╤Д╨╕╨║╨░╤Ж╨╕╤П + ╨║╨░╤В╨░╨╗╨╛╨│) |
| v2.0.0 | ╨г╨┐╤А╨░╨▓╨╗╨╡╨╜╨╕╨╡ ╨┤╨╛╤Б╤В╤Г╨┐╨╛╨╝ + ╨Р╤Г╨┤╨╕╤В Windows (╤П╨┤╤А╨╛) |
| v2.0.1 | Windows-╤Б╤В╨╡╨║ ╨┐╨╛╨╗╨╜╨╛╤Б╤В╤М╤О ╨│╨╛╤В╨╛╨▓ |
| v2.1.0 | Linux-╨░╨│╨╡╨╜╤В + ╤Г╨╜╨╕╤Д╨╕╤Ж╨╕╤А╨╛╨▓╨░╨╜╨╜╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В + WebUI ╤Д╨╕╨╗╤М╤В╤А |
| v3.0.0 | ╨г╨╜╨╕╤Д╨╕╨║╨░╤Ж╨╕╤П Manager ╨╕ WebUI: WebUI тАФ Jinja2 + ╨┐╤А╨╛╨║╤Б╨╕ API ╨╜╨░ Manager, ╨║╨╛╨╜╤Д╨╕╨│╨╕ ╨┐╨╛╤А╤В╨╛╨▓, run_all.py |
| v3.1.0 | ╨У╨╕╨▒╤А╨╕╨┤╨╜╨░╤П ╨░╤Г╤В╨╡╨╜╤В╨╕╤Д╨╕╨║╨░╤Ж╨╕╤П (JWT+Bcrypt/SPNEGO) + ╤А╨╛╨╗╨╕; S3/MinIO ╨░╨│╨╡╨╜╤В ╨░╤Г╨┤╨╕╤В╨░ (polling, ╨▒╤Г╤Д╨╡╤А, heartbeat, JWT); Windows + Linux ╨░╤Г╨┤╨╕╤В |
| v3.2.0 | ╨С╨╡╨╖╨╛╨┐╨░╤Б╨╜╨╛╤Б╤В╤М: mTLS (relaxed/strict), CertificateManager, SecretsManager, CRL, generate_certs.py/rotate_certs.py |
| v3.3.0 | ╨Р╤А╤Е╨╕╨▓╨░╤Ж╨╕╤П ╨┤╨░╨╜╨╜╤Л╤Е: retention, ╨┐╨╛╨╗╨╕╤В╨╕╨║╨╕ ╤Е╤А╨░╨╜╨╡╨╜╨╕╤П, ╤Н╨║╤Б╨┐╨╛╤А╤В JSON/CSV, WebUI ╨╜╨░╤Б╤В╤А╨╛╨╣╨║╨╕ ╤Е╤А╨░╨╜╨╡╨╜╨╕╤П |
| v3.4.0 | ╨Ш╨╜╤В╨╡╨│╤А╨░╤Ж╨╕╤П Secret Scanner (FP-╤Д╨╕╨╗╤М╤В╤А╤Л, ╨┐╤А╨╡╤Д╨╕╨╗╤М╤В╤А, ╨▒╤Г╤Д╨╡╤А╨╕╨╖╨░╤Ж╨╕╤П, ╤А╨░╤Б╤И╨╕╤А╨╡╨╜╨╜╤Л╨╡ ╤В╨╕╨┐╤Л, ╨╗╨╛╨│-╨╛╤В╤З╤С╤В) |
| v3.5.0 | ╨Ь╨░╤Б╤И╤В╨░╨▒╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡: PostgreSQL + Alembic, ╨┐╨░╤А╤В╨╕╤Ж╨╕╨╛╨╜╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡ audit_logs, Redis (╨║╤Н╤И/╨▒╤А╨╛╨║╨╡╤А/rate-limit), Celery worker/beat + Flower, docker-compose ╨┐╨╛╨╗╨╜╤Л╨╣ ╤Б╤В╨╡╨║ |
| v3.6.0 | ╨Ъ╨╛╨╜╤В╨╡╨╣╨╜╨╡╤А╨╕╨╖╨░╤Ж╨╕╤П ╨╕ ╨┤╨╡╨┐╨╗╨╛╨╣: multi-stage Dockerfile ╨┤╨╗╤П Manager/WebUI/S3/Linux-╨░╨│╨╡╨╜╤В, .dockerignore, docker-compose ╨┐╨╛╨╗╨╜╤Л╨╣ ╤Б╤В╨╡╨║ + prod overrides, ╤Б╨║╤А╨╕╨┐╤В╤Л deploy/stop/logs/status/healthcheck, docs/deployment.md |
| v3.6.1 (╨┤╨╡╨╜╤М 38.5) | Scanner ╨▓ Docker: scanner/Dockerfile (multi-stage, Tesseract + spaCy + Presidio), profile `scanner` ╨▓ compose, ╨╝╨╛╨╜╤В╨╕╤А╨╛╨▓╨░╨╜╨╕╨╡ SCAN_PATH:/scanned:ro, ╨╗╨╕╨╝╨╕╤В╤Л CPU/RAM ╨▓ prod-override |
| v3.6.2 (╨┤╨╡╨╜╤М 38.5+) | Scanner ╨▓╨╛╨╖╨▓╤А╨░╤Й╤С╨╜ ╨╜╨░ ╤Е╨╛╤Б╤В (Docker-╨║╨╛╨╜╤В╨╡╨╣╨╜╨╡╤А ╨╜╨╡ ╨╝╨╛╨╢╨╡╤В ╨┤╨╕╨╜╨░╨╝╨╕╤З╨╡╤Б╨║╨╕ ╨╝╨╛╨╜╤В╨╕╤А╨╛╨▓╨░╤В╤М ╨┐╨░╨┐╨║╨╕ ╨╕╨╖ ╨╖╨░╨┤╨░╨╜╨╕╨╣): `python run_scanner.py scanner/config/scanner_config.json`, ╤Д╨╕╨║╤Б ╤Б╨╛╤Е╤А╨░╨╜╨╡╨╜╨╕╤П `failed_files.error_type` (500 ╨┐╤А╨╕ ╨╛╤В╨┐╤А╨░╨▓╨║╨╡ ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨╛╨▓) |
| v3.7.0 (╨┤╨╡╨╜╤М 39) | ╨Ь╨╛╨╜╨╕╤В╨╛╤А╨╕╨╜╨│: heartbeat-╤В╤А╨╡╨┤ ╤Б╨║╨░╨╜╨╡╤А╨░ (╨╜╨╡ "inactive" ╨┐╤А╨╕ ╨┤╨╗╨╕╨╜╨╜╤Л╤Е ╨╖╨░╨┤╨░╨╜╨╕╤П╤Е), ╨┐╤А╨╛╨│╤А╨╡╤Б╤Б ╨╖╨░╨┤╨░╨╜╨╕╨╣ ╨╕╨╖ heartbeat (`scan_tasks.progress`), ╨╝╨╡╤В╤А╨╕╨║╨╕ Manager (HTTP/tasks/findings/celery) ╨╕ ╨░╨│╨╡╨╜╤В╨╛╨▓, Prometheus + Grafana (provisioning) + Alertmanager + ╤Н╨║╤Б╨┐╨╛╤А╤В╨╡╤А╤Л (celery/postgres/redis), docs/monitoring.md, scripts/monitoring-status.sh |

## ╨в╤А╨╡╨▒╨╛╨▓╨░╨╜╨╕╤П

- Python 3.8+
- Windows: wevtutil (╨▓╤Б╤В╤А╨╛╨╡╨╜), ╨┐╤А╨░╨▓╨░ ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╨░ ╨┤╨╗╤П ╨░╤Г╨┤╨╕╤В╨░
- Linux: watchdog, optional: paramiko (SSH-╨╝╨╛╨╜╨╕╤В╨╛╤А╨╕╨╜╨│)
- Production: Docker (PostgreSQL 16, Redis 7)
