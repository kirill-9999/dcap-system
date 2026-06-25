# -*- coding: utf-8 -*-
"""
Manager gRPC Service Implementation
"""

import uuid
import logging
from datetime import datetime
from typing import Optional

import grpc

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "proto_gen"))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

from manager.src.db.session import get_session
from manager.src.db.models import (
    Scanner, ScannerStatus, Resource, Schedule, 
    ScanTask, TaskStatus, Finding, CatalogEntry, 
    FailedFile
)

logger = logging.getLogger("dcap-manager")


class ManagerService(manager_pb2_grpc.ManagerServiceServicer):
    """Реализация gRPC сервиса Manager"""

    # ========== Scanner методы ==========

    async def Register(self, request, context):
        """Регистрация нового сканера"""
        logger.info(f"📝 Register request from: {request.scanner_name}")

        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Scanner).where(Scanner.name == request.scanner_name)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.endpoint = request.endpoint
                existing.status = ScannerStatus.ACTIVE
                existing.last_heartbeat = datetime.utcnow()
                await session.commit()
                logger.info(f"✅ Scanner '{request.scanner_name}' re-registered")
                return manager_pb2.RegisterResponse(
                    scanner_id=str(existing.id),
                    success=True,
                    message="Scanner re-registered successfully"
                )

            scanner = Scanner(
                name=request.scanner_name,
                endpoint=request.endpoint,
                status=ScannerStatus.ACTIVE,
                last_heartbeat=datetime.utcnow(),
                total_files_scanned=0,
                total_findings=0
            )
            session.add(scanner)
            await session.commit()

            logger.info(f"✅ Scanner '{request.scanner_name}' registered with ID: {scanner.id}")

            return manager_pb2.RegisterResponse(
                scanner_id=str(scanner.id),
                success=True,
                message="Scanner registered successfully"
            )

    async def Heartbeat(self, request, context):
        """Обновление статуса сканера"""
        scanner_id = request.scanner_id

        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Scanner).where(Scanner.id == int(scanner_id))
            result = await session.execute(stmt)
            scanner = result.scalar_one_or_none()

            if not scanner:
                logger.warning(f"⚠️ Heartbeat from unknown scanner: {request.scanner_id}")
                return manager_pb2.HeartbeatResponse(
                    success=False,
                    message="Scanner not found"
                )

            scanner.status = ScannerStatus.ACTIVE
            scanner.last_heartbeat = datetime.utcnow()
            await session.commit()

            logger.debug(f"💓 Heartbeat from: {scanner.name}")

            return manager_pb2.HeartbeatResponse(
                success=True,
                message="Heartbeat received"
            )

    async def GetTask(self, request, context):
        """Получение задания для сканера"""
        scanner_id = request.scanner_id
        logger.info(f"📋 GetTask called by scanner: {scanner_id}")

        async with get_session() as session:
            from sqlalchemy import select, and_
            from manager.src.db.models import ScanTask, TaskStatus, Resource

            # Проверяем, есть ли вообще PENDING задания
            count_stmt = select(ScanTask).where(ScanTask.status == TaskStatus.PENDING)
            count_result = await session.execute(count_stmt)
            pending_count = len(count_result.scalars().all())
            logger.info(f"   PENDING tasks count: {pending_count}")

            stmt = select(ScanTask, Resource).join(
                Resource, Resource.id == ScanTask.resource_id
            ).where(
                and_(
                    ScanTask.status == TaskStatus.PENDING,
                    Resource.enabled == True
                )
            ).order_by(ScanTask.created_at).limit(1)

            result = await session.execute(stmt)
            row = result.first()

            if not row:
                logger.info("ℹ️ No pending tasks found")
                return manager_pb2.GetTaskResponse(has_task=False)

            task, resource = row
            logger.info(f"   Found task: {task.id}, resource: {resource.path}")

            # Назначаем задание сканеру
            task.scanner_id = int(scanner_id)
            task.status = TaskStatus.ASSIGNED
            task.assigned_at = datetime.utcnow()

            try:
                await session.commit()
                logger.info(f"✅ Task {task.id} assigned to scanner {scanner_id}")
            except Exception as e:
                await session.rollback()
                logger.error(f"❌ Failed to assign task {task.id}: {e}")
                return manager_pb2.GetTaskResponse(has_task=False)

            return manager_pb2.GetTaskResponse(
                has_task=True,
                task_id=str(task.id),
                resource_id=str(resource.id),
                resource_path=resource.path,
                resource_type=resource.type.lower(),
                batch_size=500
            )

    # ========== Resource методы ==========

    async def CreateResource(self, request, context):
        """Создание нового ресурса"""
        logger.info(f"📁 CreateResource: {request.path} ({request.resource_type})")

        resource_type_str = request.resource_type.upper()
        
        valid_types = ["FILESYSTEM", "S3", "MINIO"]
        if resource_type_str not in valid_types:
            return manager_pb2.CreateResourceResponse(
                success=False,
                message=f"Unknown resource type: {request.resource_type}. Valid: FILESYSTEM, S3, MINIO"
            )

        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Resource).where(
                Resource.type == resource_type_str,
                Resource.path == request.path
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return manager_pb2.CreateResourceResponse(
                    success=False,
                    message=f"Resource already exists: {request.path}"
                )

            resource = Resource(
                type=resource_type_str,
                path=request.path,
                enabled=True,
                config=dict(request.config) if request.config else {}
            )
            session.add(resource)
            await session.commit()

            logger.info(f"✅ Resource created: {resource.id}")

            return manager_pb2.CreateResourceResponse(
                success=True,
                resource_id=str(resource.id),
                message="Resource created successfully"
            )

    async def ListResources(self, request, context):
        """Список ресурсов"""
        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Resource)
            if not request.include_disabled:
                stmt = stmt.where(Resource.enabled == True)

            result = await session.execute(stmt)
            resources = result.scalars().all()

            resources_list = []
            for r in resources:
                resources_list.append(manager_pb2.ResourceInfo(
                    id=str(r.id),
                    type=r.type,
                    path=r.path,
                    enabled=r.enabled,
                    last_scan_start=r.last_scan_start.isoformat() if r.last_scan_start else "",
                    last_scan_end=r.last_scan_end.isoformat() if r.last_scan_end else "",
                    created_at=r.created_at.isoformat() if r.created_at else ""
                ))

            return manager_pb2.ListResourcesResponse(resources=resources_list)

    async def GetResource(self, request, context):
        """Получить информацию о ресурсе"""
        resource_id = request.resource_id

        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Resource).where(Resource.id == int(resource_id))
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()

            if not resource:
                return manager_pb2.GetResourceResponse()

            return manager_pb2.GetResourceResponse(
                resource=manager_pb2.ResourceInfo(
                    id=str(resource.id),
                    type=resource.type,
                    path=resource.path,
                    enabled=resource.enabled,
                    last_scan_start=resource.last_scan_start.isoformat() if resource.last_scan_start else "",
                    last_scan_end=resource.last_scan_end.isoformat() if resource.last_scan_end else "",
                    created_at=resource.created_at.isoformat() if resource.created_at else ""
                )
            )

    async def DeleteResource(self, request, context):
        """Удалить ресурс"""
        resource_id = request.resource_id

        async with get_session() as session:
            from sqlalchemy import select, delete

            stmt = select(Schedule).where(Schedule.resource_id == int(resource_id))
            result = await session.execute(stmt)
            schedules = result.scalars().all()

            if schedules:
                return manager_pb2.DeleteResourceResponse(
                    success=False,
                    message=f"Cannot delete: resource has {len(schedules)} schedules"
                )

            stmt = delete(ScanTask).where(ScanTask.resource_id == int(resource_id))
            await session.execute(stmt)

            stmt = delete(Resource).where(Resource.id == int(resource_id))
            await session.execute(stmt)
            await session.commit()

            logger.info(f"🗑️ Resource deleted: {resource_id}")

            return manager_pb2.DeleteResourceResponse(
                success=True,
                message="Resource deleted successfully"
            )

    # ========== Schedule методы ==========

    async def CreateSchedule(self, request, context):
        """Создание расписания"""
        logger.info(f"📅 CreateSchedule: cron={request.cron_expression}")

        try:
            from croniter import croniter
            import time
            croniter(request.cron_expression, time.time())
        except ImportError:
            return manager_pb2.CreateScheduleResponse(
                success=False,
                message="croniter not installed. Run: pip install croniter"
            )
        except Exception as e:
            return manager_pb2.CreateScheduleResponse(
                success=False,
                message=f"Invalid cron expression: {e}"
            )

        resource_id = request.resource_id

        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Resource).where(Resource.id == int(resource_id))
            result = await session.execute(stmt)
            resource = result.scalar_one_or_none()

            if not resource:
                return manager_pb2.CreateScheduleResponse(
                    success=False,
                    message=f"Resource not found: {request.resource_id}"
                )

            from croniter import croniter
            import time
            now = time.time()
            next_run = croniter(request.cron_expression, now).get_next(datetime)

            schedule = Schedule(
                resource_id=int(resource_id),
                cron_expression=request.cron_expression,
                priority=request.priority,
                max_files_per_batch=request.max_files_per_batch,
                enabled=True,
                next_run=next_run
            )
            session.add(schedule)
            await session.commit()

            logger.info(f"✅ Schedule created: {schedule.id}")

            return manager_pb2.CreateScheduleResponse(
                success=True,
                schedule_id=str(schedule.id),
                message="Schedule created successfully"
            )

    async def ListSchedules(self, request, context):
        """Список расписаний"""
        async with get_session() as session:
            from sqlalchemy import select

            stmt = select(Schedule)
            if request.resource_id:
                stmt = stmt.where(Schedule.resource_id == int(request.resource_id))

            result = await session.execute(stmt)
            schedules = result.scalars().all()

            schedules_list = []
            for s in schedules:
                schedules_list.append(manager_pb2.ScheduleInfo(
                    id=str(s.id),
                    resource_id=str(s.resource_id),
                    cron_expression=s.cron_expression,
                    priority=s.priority,
                    max_files_per_batch=s.max_files_per_batch,
                    enabled=s.enabled,
                    last_run=s.last_run.isoformat() if s.last_run else "",
                    next_run=s.next_run.isoformat() if s.next_run else "",
                    created_at=s.created_at.isoformat() if s.created_at else ""
                ))

            return manager_pb2.ListSchedulesResponse(schedules=schedules_list)

    async def DeleteSchedule(self, request, context):
        """Удалить расписание"""
        schedule_id = request.schedule_id

        async with get_session() as session:
            from sqlalchemy import delete

            stmt = delete(Schedule).where(Schedule.id == int(schedule_id))
            result = await session.execute(stmt)
            await session.commit()

            if result.rowcount == 0:
                return manager_pb2.DeleteScheduleResponse(
                    success=False,
                    message="Schedule not found"
                )

            logger.info(f"🗑️ Schedule deleted: {schedule_id}")

            return manager_pb2.DeleteScheduleResponse(
                success=True,
                message="Schedule deleted successfully"
            )

    # ========== ReportBatch методы ==========

    async def ReportBatch(self, request_iterator, context):
        """Приём результатов сканирования"""
        logger.info("📥 ReportBatch: receiving results...")

        scanner_id = None
        task_id = None
        findings_received = 0
        catalog_entries_received = 0

        async with get_session() as session:
            async for chunk in request_iterator:
                try:
                    scanner_id = chunk.scanner_id
                    task_id = chunk.task_id

                    from sqlalchemy import select
                    stmt = select(ScanTask).where(ScanTask.id == int(task_id))
                    result = await session.execute(stmt)
                    task = result.scalar_one_or_none()

                    if not task:
                        logger.warning(f"⚠️ Task {task_id} not found")
                        continue

                    # Сохраняем находки
                    for finding in chunk.findings:
                        finding_db = Finding(
                            scanner_id=int(scanner_id),
                            task_id=int(task_id),
                            file_path=finding.file_path,
                            file_hash=finding.file_hash if finding.file_hash else None,
                            file_size=finding.file_size,
                            file_modified=datetime.fromisoformat(finding.file_modified) if finding.file_modified else None,
                            classifier_name=finding.classifier_name,
                            category=finding.category,
                            subcategory=finding.subcategory,
                            value=finding.value,
                            confidence=finding.confidence,
                            detection_method=finding.detection_method,
                            context=finding.context if finding.context else None,
                        )
                        session.add(finding_db)
                        findings_received += 1

                    # Сохраняем каталог
                    for entry in chunk.catalog:
                        catalog_db = CatalogEntry(
                            scanner_id=int(scanner_id),
                            folder_path=entry.folder_path,
                            source_type=entry.source_type,
                            classifiers=list(entry.classifiers) if entry.classifiers else [],
                            subcategories=list(entry.subcategories) if entry.subcategories else [],
                            findings_count=entry.findings_count,
                            last_seen=datetime.utcnow(),
                        )
                        session.add(catalog_db)
                        catalog_entries_received += 1

                    # Сохраняем неудачные файлы
                    for failed in chunk.failed:
                        failed_db = FailedFile(
                            scanner_id=int(scanner_id),
                            task_id=int(task_id),
                            file_path=failed.path,
                            error=failed.error,
                            error_type=failed.error_type,
                        )
                        session.add(failed_db)

                    await session.commit()
                    logger.debug(f"📦 Received: {len(chunk.findings)} findings, {len(chunk.catalog)} catalog entries")

                except Exception as e:
                    logger.error(f"❌ Error processing chunk: {e}")
                    await session.rollback()
                    return manager_pb2.ReportResponse(
                        success=False,
                        message=f"Error: {e}",
                        findings_received=0,
                        catalog_entries_received=0
                    )

            logger.info(f"✅ ReportBatch completed: {findings_received} findings, {catalog_entries_received} catalog entries")

            return manager_pb2.ReportResponse(
                success=True,
                message="Results received successfully",
                findings_received=findings_received,
                catalog_entries_received=catalog_entries_received
            )

    async def CompleteTask(self, request, context):
        """Завершение задания"""
        logger.info(f"📋 CompleteTask: task {request.task_id}")

        scanner_id = request.scanner_id
        task_id = request.task_id

        async with get_session() as session:
            from sqlalchemy import select
            from manager.src.db.models import ScanTask, TaskStatus

            stmt = select(ScanTask).where(ScanTask.id == int(task_id))
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()

            if not task:
                return manager_pb2.CompleteTaskResponse(
                    success=False,
                    message="Task not found"
                )

            if request.success:
                task.status = TaskStatus.COMPLETED
            else:
                task.status = TaskStatus.FAILED

            task.files_scanned = request.files_scanned
            task.findings_count = request.findings_count
            task.completed_at = datetime.utcnow()

            await session.commit()

            logger.info(f"✅ Task {task_id} completed: {task.files_scanned} files, {task.findings_count} findings")

            return manager_pb2.CompleteTaskResponse(
                success=True,
                message="Task completed successfully"
            )

    # ========== HealthCheck методы ==========

    async def HealthCheck(self, request, context):
        """Проверка состояния Manager"""
        from sqlalchemy import select, func
        from manager.src.db.models import Scanner, ScanTask, TaskStatus, Finding
        
        logger.info("💓 HealthCheck requested")
        
        async with get_session() as session:
            stmt_scanners = select(func.count()).select_from(Scanner).where(Scanner.status == ScannerStatus.ACTIVE)
            active_scanners = (await session.execute(stmt_scanners)).scalar() or 0
            
            stmt_pending = select(func.count()).select_from(ScanTask).where(ScanTask.status == TaskStatus.PENDING)
            pending_tasks = (await session.execute(stmt_pending)).scalar() or 0
            
            stmt_running = select(func.count()).select_from(ScanTask).where(ScanTask.status == TaskStatus.RUNNING)
            running_tasks = (await session.execute(stmt_running)).scalar() or 0
            
            stmt_completed = select(func.count()).select_from(ScanTask).where(ScanTask.status == TaskStatus.COMPLETED)
            completed_tasks = (await session.execute(stmt_completed)).scalar() or 0
            
            stmt_failed = select(func.count()).select_from(ScanTask).where(ScanTask.status == TaskStatus.FAILED)
            failed_tasks = (await session.execute(stmt_failed)).scalar() or 0
            
            stmt_findings = select(func.count()).select_from(Finding)
            total_findings = (await session.execute(stmt_findings)).scalar() or 0
            
            metrics = manager_pb2.Metrics(
                active_scanners=active_scanners,
                pending_tasks=pending_tasks,
                running_tasks=running_tasks,
                completed_tasks=completed_tasks,
                failed_tasks=failed_tasks,
                total_findings=total_findings
            )
            
            is_healthy = True
            status = "OK"
            message = "All systems operational"
            
            if pending_tasks > 100:
                is_healthy = False
                status = "DEGRADED"
                message = f"Too many pending tasks: {pending_tasks}"
            
            import time
            return manager_pb2.HealthCheckResponse(
                healthy=is_healthy,
                status=status,
                message=message,
                timestamp=int(time.time()),
                metrics=metrics
            )