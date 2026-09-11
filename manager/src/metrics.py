# manager/src/metrics.py
# Prometheus-метрики Manager (День 39).
#
# - HTTP-метрики наполняются middleware из main.py;
# - бизнес-метрики задач/findings инкрементятся из api/scanner.py
#   (track_* функции) в момент событий;
# - сканерные gauge'ы (active/heartbeat_age) обновляются лениво при
#   каждом scrape с данными из БД;
# - метрики отдаются по GET /metrics (см. main.py).

import logging
import threading
import time
from datetime import datetime

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# ============================================================
# HTTP (наполняется middleware)
# ============================================================
http_requests_total = Counter(
    "dcap_http_requests_total", "Total HTTP requests",
    ["method", "endpoint", "status"],
)
http_request_duration = Histogram(
    "dcap_http_request_duration_seconds", "HTTP request duration",
    ["method", "endpoint"],
)

# ============================================================
# Бизнес-метрики
# ============================================================
scanner_active = Gauge("dcap_scanner_active", "Active scanners", ["scanner_id"])
scanner_heartbeat_age = Gauge(
    "dcap_scanner_heartbeat_age_seconds", "Seconds since last heartbeat", ["scanner_id"]
)
task_total = Counter("dcap_tasks_total", "Total tasks", ["status"])
task_duration = Histogram("dcap_task_duration_seconds", "Task duration")
findings_total = Counter("dcap_findings_total", "Total findings", ["type"])
celery_queue_size = Gauge("dcap_celery_queue_size", "Celery queue size", ["queue"])

_scrape_lock = threading.Lock()


class MetricsMiddleware(BaseHTTPMiddleware):
    """ASGI-middleware: наполняет http_requests_total / http_request_duration."""

    async def dispatch(self, request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            try:
                endpoint = request.url.path
                http_requests_total.labels(
                    method=request.method, endpoint=endpoint, status=str(status)
                ).inc()
                http_request_duration.labels(
                    method=request.method, endpoint=endpoint
                ).observe(time.perf_counter() - start)
            except Exception:
                pass
        return response


# ============================================================
# Инкрементные обновления (вызываются из api/scanner.py)
# ============================================================

def track_task_submitted(status: str = "pending") -> None:
    task_total.labels(status=status).inc()


def track_task_completed(duration_seconds: float) -> None:
    task_duration.observe(duration_seconds)


def track_findings(category_stats: dict) -> None:
    for cat, count in (category_stats or {}).items():
        try:
            findings_total.labels(type=str(cat)).inc(int(count))
        except Exception:
            pass


# ============================================================
# Ленивое обновление gauge'ов при scrape (fail-open)
# ============================================================

def _refresh_scanner_gauges() -> None:
    try:
        from manager.src.db import session
        from manager.src.db import models

        db = session.SessionLocal()
        try:
            now = datetime.utcnow()
            scanners = db.query(models.Scanner).all()
            scanner_active.clear()
            scanner_heartbeat_age.clear()
            for s in scanners:
                active = 1 if str(s.status).lower() == "active" else 0
                scanner_active.labels(scanner_id=str(s.id)).set(active)
                if s.last_heartbeat:
                    age = max(0.0, (now - s.last_heartbeat).total_seconds())
                else:
                    age = float("inf")
                scanner_heartbeat_age.labels(scanner_id=str(s.id)).set(age)
        finally:
            db.close()
    except Exception as e:
        logger.debug("Scanner gauges refresh error: %s", e)


def _refresh_celery_queues() -> None:
    try:
        from manager.src.cache.redis_client import get_redis

        redis = get_redis()
        if not redis or not redis.available:
            return
        for queue in ["audit_events", "scanner_tasks", "retention", "reports"]:
            try:
                size = redis.llen(queue)
                if size is None or size < 0:
                    raise RuntimeError("redis unavailable")
                celery_queue_size.labels(queue=queue).set(size)
            except Exception:
                try:
                    celery_queue_size.remove(queue=queue)
                except Exception:
                    pass
    except Exception as e:
        logger.debug("Celery queue size refresh error: %s", e)


def metrics_endpoint():
    with _scrape_lock:
        _refresh_scanner_gauges()
        _refresh_celery_queues()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)