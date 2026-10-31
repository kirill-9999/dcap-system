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

# BUG-246 (v3.14.2): findings_created_total — Counter ЗА СЕССИЮ (растёт при
# создании findings в track_findings). Семантика "сколько найдено с момента
# старта процесса", а не "сколько всего в БД".
findings_created_total = Counter(
    "dcap_findings_created_total", "Findings created (session)", ["type"]
)

# BUG-246 (v3.14.2): findings_total — больше не Counter, а Gauge с РЕАЛЬНЫМ
# количеством findings в БД по типам (pii/credentials/...). Обновляется при
# каждом scrape в _refresh_findings_gauges(). Раньше это был Counter за
# сессию — Grafana/операторов вводил в заблуждение (например, credentials
# отсутствовал, пока не создан новый).
findings_total = Gauge("dcap_findings_total", "Findings in DB", ["type"])

celery_queue_size = Gauge("dcap_celery_queue_size", "Celery queue size", ["queue"])

_scrape_lock = threading.Lock()

# BUG-103 (v3.13.28): без нормализации каждый ID в пути (/api/findings/12345)
# создавал новую временную серию — бесконтрольный рост памяти Prometheus.
import re as _re

_NUM_SEG = _re.compile(r"^\d+$")
_UUID_SEG = _re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LONG_HEX_SEG = _re.compile(r"^[0-9a-fA-F]{16,}$")


def _normalize_endpoint(request) -> str:
    """Приводит путь к шаблону маршрута, чтобы исключить cardinality.

    Приоритет — template маршрута из scope (точный, бесплатный: FastAPI
    знает путь как "/api/findings/{finding_id}"). Если маршрут не найден
    (404, обработчик исключения) — путь нормализуется regex'ом: числовые
    сегменты → {id}, UUID → {uuid}.
    """
    scope = getattr(request, "scope", None) or {}
    route = scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return str(route_path)

    path = scope.get("path") or request.url.path
    parts = []
    for seg in str(path).split("/"):
        if _NUM_SEG.match(seg):
            parts.append("{id}")
        elif _UUID_SEG.match(seg):
            parts.append("{uuid}")
        elif _LONG_HEX_SEG.match(seg):
            parts.append("{hash}")
        else:
            parts.append(seg)
    return "/".join(parts)


class MetricsMiddleware(BaseHTTPMiddleware):
    """ASGI-middleware: наполняет http_requests_total / http_request_duration.

    BUG-103 (v3.13.28): добавлен в main.py ПОСЛЕ AuthMiddleware/RateLimitMiddleware,
    чтобы стоять снаружи и учитывать в т.ч. 401/403/429, которые возвращаются
    до роутера.
    """

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
                endpoint = _normalize_endpoint(request)
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
            findings_created_total.labels(type=str(cat)).inc(int(count))
        except Exception:
            pass


# ============================================================
# Ленивое обновление gauge'ов при scrape (fail-open)
# ============================================================

def _refresh_scanner_gauges() -> None:
    """Обновить gauge'ы сканеров из БД (fail-open).

    BUG-245 (v3.14.2): каждая строка обрабатывается изолированно, а ошибки
    логируются на уровне warning (раньше — debug, баг был не виден в проде).
    Строки без id пропускаются, чтобы не создавать серию scanner_id="".
    """
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
                try:
                    if s.id is None or str(s.id) == "":
                        # Дефенсивно: без id серия бессмысленна и даёт
                        # dcap_scanner_heartbeat_age_seconds{scanner_id=""}.
                        continue
                    sid = str(s.id)
                    active = 1 if str(s.status).lower() == "active" else 0
                    scanner_active.labels(scanner_id=sid).set(active)
                    if s.last_heartbeat:
                        age = max(0.0, (now - s.last_heartbeat).total_seconds())
                    else:
                        age = float("inf")
                    scanner_heartbeat_age.labels(scanner_id=sid).set(age)
                except Exception as row_err:
                    logger.warning(
                        "Scanner gauge skip (scanner_id=%s): %s",
                        getattr(s, "id", None), row_err,
                    )
        finally:
            db.close()
    except Exception as e:
        logger.warning("Scanner gauges refresh error: %s", e)


def _refresh_findings_gauges() -> None:
    """Обновить dcap_findings_total из БД по типам (BUG-246, v3.14.2).

    Должно отражать реальное количество findings в БД, включая типы,
    для которых в текущей сессии новые findings не создавались
    (например, credentials).
    """
    try:
        from sqlalchemy import func

        from manager.src.db import session
        from manager.src.db import models

        db = session.SessionLocal()
        try:
            rows = (
                db.query(
                    models.Finding.finding_type,
                    func.count(models.Finding.id),
                )
                .group_by(models.Finding.finding_type)
                .all()
            )
            findings_total.clear()
            for finding_type, count in rows:
                findings_total.labels(type=str(finding_type)).set(int(count))
        finally:
            db.close()
    except Exception as e:
        logger.warning("Findings gauges refresh error: %s", e)


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
        _refresh_findings_gauges()
        _refresh_celery_queues()
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)