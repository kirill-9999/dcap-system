# manager/src/retention/scheduler.py
import logging
import threading
import time

from ..config import get_config
from .runtime import run_retention

logger = logging.getLogger(__name__)

_scheduler_thread = None
_stop_event = threading.Event()


def _loop(interval_hours: float):
    """Фоновый цикл периодического запуска архивации."""
    interval_seconds = max(3600.0, interval_hours * 3600)
    while not _stop_event.is_set():
        try:
            logger.info("Retention scheduled run starting")
            result = run_retention(dry_run=False)
            logger.info(f"Retention scheduled run done: {result}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Retention scheduled run failed: {e}")
        _stop_event.wait(interval_seconds)


def start_scheduler():
    """Запуск фонового планировщика архивации (разовый)."""
    global _scheduler_thread
    config = get_config()
    enabled = config.get("retention", {}).get("enabled", True)
    interval_hours = config.get("retention", {}).get("interval_hours", 24)
    if not enabled:
        logger.info("Retention scheduler disabled in config")
        return None
    if _scheduler_thread is not None and _scheduler_thread.is_alive():
        return _scheduler_thread

    _stop_event.clear()
    _scheduler_thread = threading.Thread(
        target=_loop, args=(interval_hours,), name="retention-scheduler", daemon=True
    )
    _scheduler_thread.start()
    logger.info(f"Retention scheduler started every {interval_hours} hours")
    return _scheduler_thread


def stop_scheduler():
    """Остановка планировщика (graceful)."""
    _stop_event.set()
