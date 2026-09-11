# audit-agent-s3/src/metrics.py
# Prometheus-метрики S3/MinIO аудит-агента (День 39).
#
# Экспортер на :9103 для docker-compose scraping (s3_agent:9103).
# Все функции fail-open: экспорт не должен валить агента.

import logging

from prometheus_client import Counter, Gauge, start_http_server

logger = logging.getLogger(__name__)

events_collected = Counter(
    "dcap_s3_events_collected_total", "S3 events collected", []
)
events_sent = Counter(
    "dcap_s3_events_sent_total", "S3 events sent to Manager", []
)
send_errors = Counter(
    "dcap_s3_send_errors_total", "S3 events send errors", []
)
buffer_size = Gauge(
    "dcap_s3_buffer_size", "S3 agent SQLite buffer size", []
)

_started = False


def start_metrics_server(port: int = 9103) -> None:
    """Запустить HTTP-экспортер метрик в фоне (idempotent, fail-open)."""
    global _started
    try:
        if not _started:
            start_http_server(port, addr="0.0.0.0")
            _started = True
            logger.info("Metrics server started on :%s", port)
    except Exception as e:
        logger.warning("Metrics server failed to start: %s", e)


def set_buffer_size(size: int) -> None:
    try:
        buffer_size.set(size)
    except Exception:
        pass