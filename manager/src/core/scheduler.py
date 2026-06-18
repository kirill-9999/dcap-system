# -*- coding: utf-8 -*-
"""
Scheduler Engine - фоновый планировщик заданий
"""

import uuid
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

from croniter import croniter

from manager.src.db.session import get_session
from manager.src.db.models import Schedule, ScanTask, TaskStatus

logger = logging.getLogger("dcap-manager.scheduler")


class SchedulerEngine:
    """Фоновый планировщик, создающий задания по расписанию"""

    def __init__(self, check_interval_seconds: int = 60):
        """
        Args:
            check_interval_seconds: интервал проверки расписаний (сек)
        """
        self.check_interval = check_interval_seconds
        self._running = False
        self._task = None
        self._last_check = None

    async def start(self):
        """Запуск планировщика в фоновом режиме"""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"✅ Scheduler started (check interval: {self.check_interval}s)")

    async def stop(self):
        """Остановка планировщика"""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        logger.info("Scheduler stopped")

    async def _run(self):
        """Основной цикл планировщика"""
        logger.info("Scheduler loop started")

        while self._running:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

            # Ждём следующую проверку
            for _ in range(self.check_interval):
                if not self._running:
                    break
                await asyncio.sleep(1)

        logger.info("Scheduler loop finished")

    async def _check_schedules(self):
        """Проверка расписаний и создание заданий"""
        now = datetime.utcnow()
        self._last_check = now

        async with get_session() as session:
            from sqlalchemy import select

            # Находим все активные расписания, у которых next_run <= now
            stmt = select(Schedule).where(
                Schedule.enabled == True,
                Schedule.next_run <= now
            ).order_by(Schedule.priority.desc())

            result = await session.execute(stmt)
            schedules = result.scalars().all()

            if not schedules:
                logger.debug(f"No schedules due at {now.isoformat()}")
                return

            logger.info(f"📋 Found {len(schedules)} schedule(s) due for execution")

            for schedule in schedules:
                try:
                    await self._process_schedule(session, schedule)
                except Exception as e:
                    logger.error(f"Error processing schedule {schedule.id}: {e}", exc_info=True)

            await session.commit()

    async def _process_schedule(self, session, schedule: Schedule):
        """
        Обработка одного расписания — создание задания

        Args:
            session: сессия БД
            schedule: объект расписания
        """
        logger.info(f"📅 Processing schedule: {schedule.id} (cron: {schedule.cron_expression})")

        # Проверяем, есть ли уже активные задания для этого ресурса
        from sqlalchemy import select
        from manager.src.db.models import ScanTask, TaskStatus, Resource

        stmt = select(ScanTask).where(
            ScanTask.resource_id == schedule.resource_id,
            ScanTask.status.in_([TaskStatus.PENDING, TaskStatus.ASSIGNED, TaskStatus.RUNNING])
        )
        result = await session.execute(stmt)
        active_tasks = result.scalars().all()

        if active_tasks:
            logger.debug(f"⏳ Resource {schedule.resource_id} has {len(active_tasks)} active tasks, skipping")
            return

        # ЯВНО загружаем ресурс через запрос (исправление ошибки)
        stmt = select(Resource).where(Resource.id == schedule.resource_id)
        result = await session.execute(stmt)
        resource = result.scalar_one_or_none()

        if not resource:
            logger.warning(f"⚠️ Resource {schedule.resource_id} not found, disabling schedule")
            schedule.enabled = False
            return

        if not resource.enabled:
            logger.warning(f"⚠️ Resource {resource.id} is disabled, skipping")
            # Обновляем next_run, но пропускаем создание задания
            await self._update_next_run(schedule)
            return

        # Создаём задание
        import uuid
        task = ScanTask(
            id=uuid.uuid4(),
            resource_id=schedule.resource_id,
            status=TaskStatus.PENDING,
            path_filter=None,  # TODO: добавить фильтры
            files_total=0,
            files_scanned=0,
            findings_count=0,
            created_at=datetime.utcnow()
        )

        session.add(task)

        # Обновляем время последнего запуска и вычисляем следующий запуск
        schedule.last_run = datetime.utcnow()
        await self._update_next_run(schedule)

        logger.info(f"✅ Task created: {task.id} for resource {resource.path}")    

    async def _update_next_run(self, schedule: Schedule):
        """
        Вычисление и обновление следующего времени запуска

        Args:
            schedule: объект расписания
        """
        try:
            now = time.time()
            cron = croniter(schedule.cron_expression, now)
            next_run = cron.get_next(datetime)
            schedule.next_run = next_run
            logger.debug(f"📅 Schedule {schedule.id} next_run: {next_run.isoformat()}")
        except Exception as e:
            logger.error(f"❌ Failed to calculate next_run for schedule {schedule.id}: {e}")
            # Отключаем расписание при ошибке
            schedule.enabled = False
            logger.warning(f"⚠️ Schedule {schedule.id} disabled due to cron error")

    def get_status(self) -> dict:
        """Получить статус планировщика"""
        return {
            "running": self._running,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "check_interval": self.check_interval
        }