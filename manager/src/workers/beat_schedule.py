# manager/src/workers/beat_schedule.py
"""Расписание Celery Beat для Manager (День 36-37).

Отдельный модуль позволяет редактировать расписание без правки celery_app.
Интегрируется в app.conf.beat_schedule (см. celery_app.py).
"""
from celery.schedules import crontab

# Retention: ежедневный прогон архивации в 03:00 UTC (очередь retention).
# Интервал из конфига (retention.interval_hours) используется для
# интервального режима на больших интервалах; crontab фиксирован на 3:00.
retention_schedule = crontab(minute=0, hour=3)

# Sweep расписаний сканера: каждые 2 часа (очередь scanner_tasks).
scanner_sweep = crontab(minute=0, hour="*/2")

# Ротация логов: ежедневно в 03:30 UTC (очередь retention).
log_rotation = crontab(minute=30, hour=3)

BEAT_SCHEDULE = {
    "retention-daily": {
        "task": "manager.src.workers.tasks.run_retention",
        "schedule": retention_schedule,
        "options": {"queue": "retention"},
    },
    "scanner-sweep": {
        "task": "manager.src.workers.tasks.sweep_scheduled_scans",
        "schedule": scanner_sweep,
        "options": {"queue": "scanner_tasks"},
    },
    "log-rotation-daily": {
        "task": "manager.src.workers.tasks.clean_log_rotation_task",
        "schedule": log_rotation,
        "options": {"queue": "retention"},
    },
}