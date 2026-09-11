#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# audit-agent-linux/metrics.py
# Prometheus-метрики Linux-агента аудита (День 39).
#
# Экспортер на :9102 для docker-compose scraping (audit_agent_linux:9102).
# Все функции fail-open: экспорт не должен валить агента.

import logging

from prometheus_client import Counter, Gauge, start_http_server

logger = logging.getLogger(__name__)

events_collected = Counter(
    "dcap_linux_events_collected_total", "Linux agent events collected", []
)
events_sent = Counter(
    "dcap_linux_events_sent_total", "Linux agent events sent to Manager", []
)
send_errors = Counter(
    "dcap_linux_send_errors_total", "Linux agent events send errors", []
)
buffer_size = Gauge(
    "dcap_linux_buffer_size", "Linux agent SQLite buffer size", []
)

_started = False


def start_metrics_server(port: int = 9102) -> None:
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