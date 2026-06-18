# -*- coding: utf-8 -*-
"""
Manager gRPC Service Implementation
"""

import uuid
import logging
from datetime import datetime

import grpc

# ДОБАВЛЯЕМ ПУТЬ ДЛЯ ИМПОРТА
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "proto_gen"))

import dcap.manager_pb2 as manager_pb2
import dcap.manager_pb2_grpc as manager_pb2_grpc

from manager.src.db.session import get_session
from manager.src.db.models import Scanner, ScannerStatus

logger = logging.getLogger("dcap-manager")


class ManagerService(manager_pb2_grpc.ManagerServicer):
    """Реализация gRPC сервиса Manager"""
    
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
                id=uuid.uuid4(),
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
        try:
            scanner_id = uuid.UUID(request.scanner_id)
        except ValueError:
            logger.warning(f"⚠️ Invalid scanner_id: {request.scanner_id}")
            return manager_pb2.HeartbeatResponse(
                success=False,
                message="Invalid scanner_id format"
            )
        
        async with get_session() as session:
            from sqlalchemy import select
            
            stmt = select(Scanner).where(Scanner.id == scanner_id)
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
        try:
            scanner_id = uuid.UUID(request.scanner_id)
        except ValueError:
            return manager_pb2.GetTaskResponse(has_task=False)
        
        async with get_session() as session:
            from sqlalchemy import select
            from manager.src.db.models import ScanTask, TaskStatus
            
            stmt = select(ScanTask).where(
                ScanTask.status == TaskStatus.PENDING
            ).order_by(ScanTask.created_at).limit(1)
            
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
            
            if not task:
                return manager_pb2.GetTaskResponse(has_task=False)
            
            task.scanner_id = scanner_id
            task.status = TaskStatus.ASSIGNED
            task.assigned_at = datetime.utcnow()
            await session.commit()
            
            resource = task.resource
            
            logger.info(f"📋 Task {task.id} assigned to scanner {scanner_id}")
            
            return manager_pb2.GetTaskResponse(
                has_task=True,
                task_id=str(task.id),
                resource_id=str(resource.id),
                resource_path=resource.path,
                resource_type=resource.type.value,
                batch_size=500
            )