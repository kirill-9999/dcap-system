from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from typing import Optional, List
import os
import sys

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from manager.src.db.models import Finding, Scanner, ScanTask, Resource
from webui.api.schemas import (
    FindingResponse, TaskResponse, ScannerResponse, 
    ResourceResponse, StatsResponse
)
from webui.config import DATABASE_URL

router = APIRouter(prefix="/api")

# Настройка базы данных
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# === ЭНДПОИНТЫ ===

@router.get("/stats")
async def get_stats():
    """Получить общую статистику системы"""
    async with AsyncSessionLocal() as session:
        # Общее количество находок
        total_findings = await session.scalar(select(func.count(Finding.id))) or 0
        
        # Активные сканеры (heartbeat < 60 секунд)
        active_scanners = await session.scalar(
            select(func.count(Scanner.id)).where(
                Scanner.last_heartbeat > datetime.now() - timedelta(seconds=60)
            )
        ) or 0
        
        # Задания по статусам
        pending_tasks = await session.scalar(
            select(func.count(ScanTask.id)).where(ScanTask.status == "PENDING")
        ) or 0
        
        completed_tasks = await session.scalar(
            select(func.count(ScanTask.id)).where(ScanTask.status == "COMPLETED")
        ) or 0
        
        failed_tasks = await session.scalar(
            select(func.count(ScanTask.id)).where(ScanTask.status == "FAILED")
        ) or 0
        
        # Всего отсканированных файлов
        total_files = await session.scalar(
            select(func.sum(ScanTask.files_scanned))
        ) or 0
        
        # Находки по категориям
        findings_by_category = {}
        result = await session.execute(
            select(Finding.category, func.count(Finding.id))
            .group_by(Finding.category)
        )
        for category, count in result:
            findings_by_category[category] = count
        
        # Находки по сканерам
        findings_by_scanner = {}
        result = await session.execute(
            select(Scanner.name, func.count(Finding.id))
            .join(Finding, Finding.scanner_id == Scanner.id)
            .group_by(Scanner.name)
        )
        for name, count in result:
            findings_by_scanner[name] = count
        
        # Задания по статусам
        tasks_by_status = {}
        result = await session.execute(
            select(ScanTask.status, func.count(ScanTask.id))
            .group_by(ScanTask.status)
        )
        for status, count in result:
            tasks_by_status[status] = count
        
        return StatsResponse(
            total_findings=total_findings,
            active_scanners=active_scanners,
            pending_tasks=pending_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
            total_files_scanned=int(total_files),
            findings_by_category=findings_by_category,
            findings_by_scanner=findings_by_scanner,
            tasks_by_status=tasks_by_status
        )

@router.get("/findings")
async def get_findings(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None,
    min_confidence: Optional[float] = Query(None, ge=0, le=1)
):
    """Получить список находок с фильтрацией"""
    async with AsyncSessionLocal() as session:
        query = select(Finding)
        
        # Применяем фильтры
        if category:
            query = query.where(Finding.category == category)
        if file_path:
            query = query.where(Finding.file_path.contains(file_path))
        if scanner_id:
            query = query.where(Finding.scanner_id == scanner_id)
        if min_confidence is not None:
            query = query.where(Finding.confidence >= min_confidence)
        
        # Сортировка по ID (новые сверху)
        query = query.order_by(desc(Finding.id)).limit(limit).offset(offset)
        
        result = await session.execute(query)
        findings = result.scalars().all()
        
        return [FindingResponse.model_validate(f) for f in findings]

@router.get("/findings/{finding_id}")
async def get_finding(finding_id: int):
    """Получить детальную информацию о находке"""
    async with AsyncSessionLocal() as session:
        finding = await session.get(Finding, finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")
        
        # Получаем информацию о задании и сканере
        task = await session.get(ScanTask, finding.task_id)
        scanner = await session.get(Scanner, finding.scanner_id)
        
        return {
            "finding": FindingResponse.model_validate(finding),
            "task": TaskResponse.model_validate(task) if task else None,
            "scanner": ScannerResponse.model_validate(scanner) if scanner else None
        }

@router.get("/findings/count")
async def get_findings_count(
    category: Optional[str] = None,
    file_path: Optional[str] = None,
    scanner_id: Optional[int] = None
):
    """Получить количество находок с фильтрацией"""
    async with AsyncSessionLocal() as session:
        query = select(func.count(Finding.id))
        
        if category:
            query = query.where(Finding.category == category)
        if file_path:
            query = query.where(Finding.file_path.contains(file_path))
        if scanner_id:
            query = query.where(Finding.scanner_id == scanner_id)
        
        count = await session.scalar(query) or 0
        return {"count": count}

@router.get("/tasks")
async def get_tasks(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    resource_id: Optional[int] = None
):
    """Получить список заданий"""
    async with AsyncSessionLocal() as session:
        query = select(ScanTask)
        
        if status:
            query = query.where(ScanTask.status == status)
        if resource_id:
            query = query.where(ScanTask.resource_id == resource_id)
        
        query = query.order_by(desc(ScanTask.created_at)).limit(limit).offset(offset)
        
        result = await session.execute(query)
        tasks = result.scalars().all()
        
        return [TaskResponse.model_validate(t) for t in tasks]

@router.get("/tasks/{task_id}")
async def get_task(task_id: int):
    """Получить детальную информацию о задании"""
    async with AsyncSessionLocal() as session:
        task = await session.get(ScanTask, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Получаем находки для этого задания
        findings_result = await session.execute(
            select(Finding).where(Finding.task_id == task_id).limit(100)
        )
        findings = findings_result.scalars().all()
        
        # Получаем ресурс и сканер
        resource = await session.get(Resource, task.resource_id)
        scanner = await session.get(Scanner, task.scanner_id) if task.scanner_id else None
        
        return {
            "task": TaskResponse.model_validate(task),
            "findings": [FindingResponse.model_validate(f) for f in findings],
            "findings_count": len(findings),
            "resource": ResourceResponse.model_validate(resource) if resource else None,
            "scanner": ScannerResponse.model_validate(scanner) if scanner else None
        }

@router.get("/scanners")
async def get_scanners():
    """Получить список всех сканеров"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Scanner).order_by(Scanner.id)
        )
        scanners = result.scalars().all()
        return [ScannerResponse.model_validate(s) for s in scanners]

@router.get("/scanners/{scanner_id}")
async def get_scanner(scanner_id: int):
    """Получить информацию о сканере"""
    async with AsyncSessionLocal() as session:
        scanner = await session.get(Scanner, scanner_id)
        if not scanner:
            raise HTTPException(status_code=404, detail="Scanner not found")
        return ScannerResponse.model_validate(scanner)

@router.get("/resources")
async def get_resources(enabled_only: bool = False):
    """Получить список ресурсов"""
    async with AsyncSessionLocal() as session:
        query = select(Resource)
        if enabled_only:
            query = query.where(Resource.enabled == True)
        
        result = await session.execute(query.order_by(Resource.id))
        resources = result.scalars().all()
        return [ResourceResponse.model_validate(r) for r in resources]

@router.get("/categories")
async def get_categories():
    """Получить список всех уникальных категорий находок"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Finding.category).distinct().order_by(Finding.category)
        )
        return [row[0] for row in result]

@router.get("/classifiers")
async def get_classifiers():
    """Получить список всех уникальных классификаторов"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Finding.classifier_name).distinct().order_by(Finding.classifier_name)
        )
        return [row[0] for row in result]