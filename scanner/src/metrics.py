#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Prometheus-метрики сканера (День 39).

Сканер запускается на хосте (v3.6.2) — HTTP-экспортер на :9101.
Промetheus собирает через host.docker.internal:9101 (>scrape_configs).
"""

import logging

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)

# Счётчики/гистограммы/gauges для сканера.
files_scanned = Counter(
    "dcap_scanner_files_scanned_total", "Files scanned", ["scanner_id"]
)
findings = Counter(
    "dcap_scanner_findings_total", "Findings", ["scanner_id", "type"]
)
scan_duration = Histogram(
    "dcap_scanner_file_duration_seconds", "Per-file scan duration", ["scanner_id"]
)
scan_errors = Counter(
    "dcap_scanner_errors_total", "Scan errors", ["scanner_id", "error_type"]
)
current_task = Gauge(
    "dcap_scanner_current_task", "Current task id", ["scanner_id"]
)

_started = False


def start_metrics_server(scanner_id: int, port: int = 9101) -> None:
    """Запустить HTTP-экспортер метрик в фоне (idempotent)."""
    global _started
    try:
        if not _started:
            start_http_server(port, addr="0.0.0.0")
            _started = True
            logger.info("Metrics server started on :%s (scanner_id=%s)", port, scanner_id)
    except Exception as e:
        # Fail-open: экспортер не должен валить сканер.
        logger.warning("Metrics server failed to start: %s", e)


def set_current_task(scanner_id: int, task_id: int) -> None:
    current_task.labels(scanner_id=str(scanner_id)).set(task_id)


def clear_current_task(scanner_id: int) -> None:
    current_task.remove(scanner_id=str(scanner_id))