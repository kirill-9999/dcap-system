# manager/src/workers/celery_app.py
"""Celery app Manager (День 36-37).

Брокер: Redis (REDIS_URL / config redis.url). Если брокер недоступен,
задачи не могут быть выполнены, но Manager продолжает работу
(auth/rate-limit защищены fallback'ом — см. core/rate_limit.py).
Очереди:
  - audit_events   — приём событий аудита из агента (асинхронная запись)
  - scanner_tasks  — планирование/управление задачами сканера
  - retention      — периодическая архивация (Celery Beat)
  - reports        — генерация отчётов (PDF/XLSX)
"""
import logging

from celery import Celery

from ..config import get_config
from .beat_schedule import BEAT_SCHEDULE

logger = logging.getLogger(__name__)

_cfg = get_config()
_redis_cfg = _cfg.get("redis", {})
_broker_url = _redis_cfg.get("url", "redis://localhost:6379/0")
if _redis_cfg.get("password"):
    # Включение пароля в broker URL (redis://:password@host:port/db)
    try:
        from urllib.parse import urlsplit, urlunsplit, quote

        parts = urlsplit(_broker_url)
        netloc = f":{quote(_redis_cfg['password'], safe='')}@{parts.hostname or 'localhost'}"
        if parts.port:
            netloc += f":{parts.port}"
        _broker_url = urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:  # noqa: BLE001
        logger.warning("Не удалось добавить пароль в broker URL", exc_info=True)

app = Celery(
    "dcap_manager",
    broker=_broker_url,
    backend=_broker_url,
    include=[
        "manager.src.workers.tasks",
    ],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    result_expires=3600,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    broker_connection_retry_on_startup=True,
    task_default_queue="audit_events",
    task_routes={
        "manager.src.workers.tasks.process_audit_event": {"queue": "audit_events"},
        "manager.src.workers.tasks.enqueue_audit_batch": {"queue": "audit_events"},
        "manager.src.workers.tasks.assign_scanner_task": {"queue": "scanner_tasks"},
        "manager.src.workers.tasks.process_scanner_task": {"queue": "scanner_tasks"},
        "manager.src.workers.tasks.scan_resource": {"queue": "scanner_tasks"},
        "manager.src.workers.tasks.run_retention": {"queue": "retention"},
        "manager.src.workers.tasks.clean_log_rotation_task": {"queue": "retention"},
        "manager.src.workers.tasks.generate_report": {"queue": "reports"},
        "manager.src.workers.tasks.export_audit_report": {"queue": "reports"},
    },
)

# ============================================================
# РАСПИСАНИЕ (Celery Beat)
# ============================================================

app.conf.beat_schedule = BEAT_SCHEDULE


def get_celery_app() -> Celery:
    return app