📋 ТЗ — ДЕНЬ 35: АРХИВАЦИЯ ДАННЫХ
Файл: prompts/tz/day_35_data_retention.md
Дата: 02.09.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Реализовать автоматическую архивацию и очистку данных для предотвращения переполнения БД и обеспечения соответствия политикам хранения:

Ротация логов — автоматическая ротация файлов логов (уже есть в Дне 32)

Архивация событий — перемещение старых событий в архивные таблицы

Очистка находок — удаление устаревших находок

Очистка завершенных задач — удаление старых задач сканирования

Политика хранения — настраиваемый срок хранения данных (TTL)

Экспорт в архив — выгрузка старых данных в файлы (CSV/JSON)

API — ручной запуск архивации и просмотр статуса

📁 СТРУКТУРА ИЗМЕНЕНИЙ
text
manager/src/
├── retention/
│   ├── __init__.py
│   ├── policies.py            # Политики хранения (TTL для разных типов)
│   ├── archiver.py            # Архивация событий (перемещение в архивные таблицы)
│   ├── cleaner.py             # Очистка устаревших данных
│   ├── exporter.py            # Экспорт в CSV/JSON
│   └── scheduler.py           # Периодические задачи (Celery Beat)
├── api/
│   └── retention.py           # API эндпоинты для управления архивацией
├── db/
│   ├── models.py              # ОБНОВЛЕН: + архивные модели
│   └── migrations/
│       └── versions/
│           └── 002_add_archive_tables.py   # Миграция для архивных таблиц
└── workers/
    └── tasks.py               # ОБНОВЛЕН: + задачи архивации

webui/templates/
└── settings.html              # ОБНОВЛЕН: + настройки хранения данных
📋 ПОЛИТИКИ ХРАНЕНИЯ
Параметры по умолчанию
Тип данных	TTL	Действие	Параметр
Аудит-события	90 дней	Архивация → удаление	retention.audit_events.ttl_days
Архивные события	365 дней	Удаление	retention.audit_events.archive_ttl_days
Находки	180 дней	Удаление	retention.findings.ttl_days
Завершенные задачи	30 дней	Удаление	retention.tasks.ttl_days
Логи	30 дней	Ротация	retention.logs.rotate_days
Конфигурация
json
// manager/config/config.json (дополнение)
{
    // ... существующие секции ...
    "retention": {
        "enabled": true,
        "interval_hours": 24,
        "audit_events": {
            "ttl_days": 90,
            "archive_ttl_days": 365,
            "archive_enabled": true,
            "archive_table": "audit_logs_archive"
        },
        "findings": {
            "ttl_days": 180
        },
        "tasks": {
            "ttl_days": 30
        },
        "logs": {
            "rotate_days": 30,
            "max_size_mb": 100
        },
        "export": {
            "enabled": true,
            "format": "json",
            "path": "data/archive/"
        }
    }
}
🗄️ МОДЕЛИ БД
Архивные таблицы
python
# manager/src/db/models.py (дополнение)

class AuditLogArchive(Base):
    """Архивная таблица для аудит-событий"""
    __tablename__ = "audit_logs_archive"
    
    id = Column(BigInteger, primary_key=True)
    agent_id = Column(Integer, ForeignKey("audit_agents.id"), index=True)
    event_type = Column(String(50), nullable=False)
    event_source = Column(String(50), nullable=False)
    user = Column(String(200))
    user_sid = Column(String(100))
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500))
    source_host = Column(String(100))
    metadata = Column(JSONB)
    created_at = Column(DateTime, nullable=False, index=True)
    archived_at = Column(DateTime, default=datetime.utcnow)

class FindingArchive(Base):
    """Архивная таблица для находок"""
    __tablename__ = "findings_archive"
    
    id = Column(BigInteger, primary_key=True)
    resource_id = Column(Integer, ForeignKey("resources.id"))
    scanner_id = Column(Integer, ForeignKey("scanners.id"))
    category = Column(String(50))
    severity = Column(String(20))
    file_path = Column(String(500))
    line_number = Column(Integer)
    content = Column(Text)
    metadata = Column(JSONB)
    created_at = Column(DateTime)
    archived_at = Column(DateTime, default=datetime.utcnow)
Миграция
python
# manager/src/db/migrations/versions/002_add_archive_tables.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    # AuditLogArchive
    op.create_table(
        'audit_logs_archive',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_source', sa.String(length=50), nullable=False),
        sa.Column('user', sa.String(length=200), nullable=True),
        sa.Column('user_sid', sa.String(length=100), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('old_path', sa.String(length=500), nullable=True),
        sa.Column('source_host', sa.String(length=100), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_archive_created', 'audit_logs_archive', ['created_at'])
    
    # FindingArchive
    op.create_table(
        'findings_archive',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('scanner_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=True),
        sa.Column('line_number', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('findings_archive')
    op.drop_table('audit_logs_archive')
📦 МОДУЛИ
1. policies.py — Политики хранения
python
# manager/src/retention/policies.py
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class RetentionPolicy:
    """Политика хранения для каждого типа данных"""
    
    def __init__(self, config: dict):
        self.config = config
        self._policies = {}
        self._load_policies()
    
    def _load_policies(self):
        """Загрузка политик из конфига"""
        retention_config = self.config.get("retention", {})
        
        # Аудит-события
        audit_config = retention_config.get("audit_events", {})
        self._policies["audit_events"] = {
            "ttl_days": audit_config.get("ttl_days", 90),
            "archive_ttl_days": audit_config.get("archive_ttl_days", 365),
            "archive_enabled": audit_config.get("archive_enabled", True)
        }
        
        # Находки
        findings_config = retention_config.get("findings", {})
        self._policies["findings"] = {
            "ttl_days": findings_config.get("ttl_days", 180)
        }
        
        # Задачи
        tasks_config = retention_config.get("tasks", {})
        self._policies["tasks"] = {
            "ttl_days": tasks_config.get("ttl_days", 30)
        }
        
        # Логи
        logs_config = retention_config.get("logs", {})
        self._policies["logs"] = {
            "rotate_days": logs_config.get("rotate_days", 30),
            "max_size_mb": logs_config.get("max_size_mb", 100)
        }
        
        logger.info(f"Loaded retention policies: {list(self._policies.keys())}")
    
    def get_ttl(self, data_type: str) -> Optional[int]:
        """Получение TTL для типа данных"""
        policy = self._policies.get(data_type)
        if policy:
            return policy.get("ttl_days")
        return None
    
    def get_cutoff_date(self, data_type: str) -> Optional[datetime]:
        """Получение даты отсечения для типа данных"""
        ttl = self.get_ttl(data_type)
        if ttl is not None:
            return datetime.utcnow() - timedelta(days=ttl)
        return None
2. archiver.py — Архивация событий
python
# manager/src/retention/archiver.py
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging
from typing import Dict

from ..db.models import AuditLog, Finding, AuditLogArchive, FindingArchive
from .policies import RetentionPolicy

logger = logging.getLogger(__name__)

class Archiver:
    """Архивация данных (перемещение в архивные таблицы)"""
    
    def __init__(self, db: Session, policy: RetentionPolicy):
        self.db = db
        self.policy = policy
    
    def archive_audit_events(self, dry_run: bool = False) -> Dict[str, int]:
        """Архивация аудит-событий"""
        cutoff = self.policy.get_cutoff_date("audit_events")
        if not cutoff:
            return {"archived": 0, "error": "No TTL configured"}
        
        try:
            # 1. Получение событий для архивации
            events = self.db.query(AuditLog).filter(
                AuditLog.created_at < cutoff
            ).limit(10000).all()
            
            if not events:
                logger.info("No audit events to archive")
                return {"archived": 0}
            
            logger.info(f"Archiving {len(events)} audit events")
            
            if dry_run:
                return {"archived": len(events), "dry_run": True}
            
            # 2. Копирование в архивную таблицу
            for event in events:
                archive = AuditLogArchive(
                    agent_id=event.agent_id,
                    event_type=event.event_type,
                    event_source=event.event_source,
                    user=event.user,
                    user_sid=event.user_sid,
                    file_path=event.file_path,
                    old_path=event.old_path,
                    source_host=event.source_host,
                    metadata=event.metadata,
                    created_at=event.created_at,
                    archived_at=datetime.utcnow()
                )
                self.db.add(archive)
            
            self.db.flush()
            
            # 3. Удаление оригиналов
            for event in events:
                self.db.delete(event)
            
            self.db.commit()
            
            logger.info(f"Archived {len(events)} audit events")
            return {"archived": len(events)}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error archiving audit events: {e}")
            return {"archived": 0, "error": str(e)}
    
    def archive_findings(self, dry_run: bool = False) -> Dict[str, int]:
        """Архивация находок"""
        cutoff = self.policy.get_cutoff_date("findings")
        if not cutoff:
            return {"archived": 0, "error": "No TTL configured"}
        
        try:
            findings = self.db.query(Finding).filter(
                Finding.created_at < cutoff
            ).limit(10000).all()
            
            if not findings:
                return {"archived": 0}
            
            logger.info(f"Archiving {len(findings)} findings")
            
            if dry_run:
                return {"archived": len(findings), "dry_run": True}
            
            for finding in findings:
                archive = FindingArchive(
                    resource_id=finding.resource_id,
                    scanner_id=finding.scanner_id,
                    category=finding.category,
                    severity=finding.severity,
                    file_path=finding.file_path,
                    line_number=finding.line_number,
                    content=finding.content,
                    metadata=finding.metadata,
                    created_at=finding.created_at,
                    archived_at=datetime.utcnow()
                )
                self.db.add(archive)
            
            self.db.flush()
            
            for finding in findings:
                self.db.delete(finding)
            
            self.db.commit()
            
            logger.info(f"Archived {len(findings)} findings")
            return {"archived": len(findings)}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error archiving findings: {e}")
            return {"archived": 0, "error": str(e)}
3. cleaner.py — Очистка данных
python
# manager/src/retention/cleaner.py
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from typing import Dict

from ..db.models import AuditLogArchive, ScanTask, TaskStatus
from .policies import RetentionPolicy

logger = logging.getLogger(__name__)

class Cleaner:
    """Очистка данных (удаление устаревших)"""
    
    def __init__(self, db: Session, policy: RetentionPolicy):
        self.db = db
        self.policy = policy
    
    def clean_archive_tables(self, dry_run: bool = False) -> Dict[str, int]:
        """Очистка архивных таблиц"""
        cutoff = self.policy.get_cutoff_date("audit_events")
        if not cutoff:
            return {"deleted": 0, "error": "No TTL configured"}
        
        # Используем archive_ttl_days
        retention_config = self.policy.config.get("retention", {})
        audit_config = retention_config.get("audit_events", {})
        archive_ttl = audit_config.get("archive_ttl_days", 365)
        archive_cutoff = datetime.utcnow() - timedelta(days=archive_ttl)
        
        try:
            # Удаление из архивной таблицы
            count = self.db.query(AuditLogArchive).filter(
                AuditLogArchive.created_at < archive_cutoff
            ).count()
            
            if dry_run:
                return {"deleted": count, "dry_run": True}
            
            deleted = self.db.query(AuditLogArchive).filter(
                AuditLogArchive.created_at < archive_cutoff
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Cleaned {deleted} archived audit events")
            return {"deleted": deleted}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning archive: {e}")
            return {"deleted": 0, "error": str(e)}
    
    def clean_completed_tasks(self, dry_run: bool = False) -> Dict[str, int]:
        """Очистка завершенных задач"""
        cutoff = self.policy.get_cutoff_date("tasks")
        if not cutoff:
            return {"deleted": 0}
        
        try:
            count = self.db.query(ScanTask).filter(
                ScanTask.status == TaskStatus.COMPLETED,
                ScanTask.completed_at < cutoff
            ).count()
            
            if dry_run:
                return {"deleted": count, "dry_run": True}
            
            deleted = self.db.query(ScanTask).filter(
                ScanTask.status == TaskStatus.COMPLETED,
                ScanTask.completed_at < cutoff
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Cleaned {deleted} completed tasks")
            return {"deleted": deleted}
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cleaning tasks: {e}")
            return {"deleted": 0, "error": str(e)}
4. exporter.py — Экспорт в архивные файлы
python
# manager/src/retention/exporter.py
import json
import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from sqlalchemy.orm import Session
import logging

from ..db.models import AuditLogArchive, FindingArchive

logger = logging.getLogger(__name__)

class Exporter:
    """Экспорт архивных данных в файлы"""
    
    def __init__(self, config: dict):
        self.config = config
        self.export_config = config.get("retention", {}).get("export", {})
        self.enabled = self.export_config.get("enabled", True)
        self.format = self.export_config.get("format", "json")
        self.export_dir = Path(self.export_config.get("path", "data/archive/"))
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def export_archived_audit_events(self, db: Session, limit: int = 10000) -> Dict[str, any]:
        """Экспорт архивных аудит-событий"""
        if not self.enabled:
            return {"exported": 0, "error": "Export disabled"}
        
        try:
            events = db.query(AuditLogArchive).order_by(
                AuditLogArchive.created_at
            ).limit(limit).all()
            
            if not events:
                return {"exported": 0}
            
            filename = self.export_dir / f"audit_archive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{self.format}"
            
            if self.format == "json":
                self._export_json(filename, [e.to_dict() for e in events])
            else:
                self._export_csv(filename, [e.to_dict() for e in events])
            
            # Помечаем как экспортированные (добавим поле exported_at)
            # (реализация опционально)
            
            logger.info(f"Exported {len(events)} audit events to {filename}")
            return {"exported": len(events), "file": str(filename)}
            
        except Exception as e:
            logger.error(f"Error exporting audit events: {e}")
            return {"exported": 0, "error": str(e)}
    
    def _export_json(self, filename: Path, data: List[dict]):
        """Экспорт в JSON"""
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def _export_csv(self, filename: Path, data: List[dict]):
        """Экспорт в CSV"""
        if not data:
            return
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
5. scheduler.py — Периодические задачи
python
# manager/src/retention/scheduler.py
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..workers.celery_app import celery_app
from .policies import RetentionPolicy
from .archiver import Archiver
from .cleaner import Cleaner
from .exporter import Exporter

logger = logging.getLogger(__name__)

@celery_app.task(name="retention.run_retention")
def run_retention(dry_run: bool = False):
    """Запуск полного цикла архивации и очистки"""
    logger.info(f"Starting retention job (dry_run={dry_run})")
    
    with get_db() as db:
        # Загрузка политик
        from ..config import config
        policy = RetentionPolicy(config)
        
        # Архивация
        archiver = Archiver(db, policy)
        result_audit = archiver.archive_audit_events(dry_run)
        result_findings = archiver.archive_findings(dry_run)
        
        # Очистка
        cleaner = Cleaner(db, policy)
        result_clean = cleaner.clean_archive_tables(dry_run)
        result_tasks = cleaner.clean_completed_tasks(dry_run)
        
        # Экспорт
        exporter = Exporter(config)
        result_export = exporter.export_archived_audit_events(db)
        
        return {
            "archived_audit": result_audit,
            "archived_findings": result_findings,
            "cleaned_archive": result_clean,
            "cleaned_tasks": result_tasks,
            "exported": result_export,
            "timestamp": datetime.utcnow().isoformat()
        }

@celery_app.on_after_configure.connect
def setup_periodic_retention(sender, **kwargs):
    """Настройка периодического запуска архивации"""
    from ..config import config
    interval_hours = config.get("retention", {}).get("interval_hours", 24)
    
    sender.add_periodic_task(
        interval_hours * 3600,  # в секундах
        run_retention.s(),
        name="retention.run_retention"
    )
    
    logger.info(f"Retention scheduled every {interval_hours} hours")
6. API эндпоинты
python
# manager/src/api/retention.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..auth.dependencies import require_admin
from ..db.session import get_db
from ..retention.policies import RetentionPolicy
from ..retention.archiver import Archiver
from ..retention.cleaner import Cleaner
from ..retention.exporter import Exporter
from ..retention.scheduler import run_retention
from ..config import config

router = APIRouter(prefix="/api/retention", tags=["retention"])

@router.get("/policies")
async def get_retention_policies(
    admin: User = Depends(require_admin)
):
    """Получение текущих политик хранения"""
    policy = RetentionPolicy(config)
    return {
        "policies": policy._policies,
        "interval_hours": config.get("retention", {}).get("interval_hours", 24)
    }

@router.post("/run")
async def run_retention_manual(
    dry_run: bool = False,
    admin: User = Depends(require_admin)
):
    """Ручной запуск архивации и очистки"""
    result = run_retention.delay(dry_run=dry_run)
    return {
        "task_id": result.id,
        "status": "started",
        "dry_run": dry_run
    }

@router.get("/status")
async def get_retention_status(
    admin: User = Depends(require_admin)
):
    """Статус последней архивации"""
    # (можно хранить в отдельной таблице)
    return {
        "last_run": None,  # TODO: хранить в БД
        "next_run": "scheduled"
    }

@router.post("/export")
async def export_archive(
    data_type: str = "audit",
    limit: int = 10000,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Ручной экспорт архивных данных"""
    exporter = Exporter(config)
    
    if data_type == "audit":
        result = exporter.export_archived_audit_events(db, limit)
    else:
        raise HTTPException(400, f"Unsupported data type: {data_type}")
    
    return result
🌐 WEBUI — НАСТРОЙКИ ХРАНЕНИЯ
settings.html (обновленный)
html
<!-- webui/templates/settings.html (дополнение) -->

<!-- Вкладка: Хранение данных -->
<div class="tab-pane fade" id="retentionTab">
    <h3><i class="fas fa-database"></i> Политики хранения данных</h3>
    
    <div class="card">
        <div class="card-body">
            <div class="retention-grid">
                <div class="retention-item">
                    <h5>Аудит-события</h5>
                    <div class="row">
                        <div class="col">
                            <label>Срок хранения (дни)</label>
                            <input type="number" id="retentionAuditTtl" 
                                   value="90" class="form-control">
                        </div>
                        <div class="col">
                            <label>Архивный срок (дни)</label>
                            <input type="number" id="retentionAuditArchiveTtl" 
                                   value="365" class="form-control">
                        </div>
                    </div>
                </div>
                
                <div class="retention-item">
                    <h5>Находки</h5>
                    <div class="row">
                        <div class="col">
                            <label>Срок хранения (дни)</label>
                            <input type="number" id="retentionFindingsTtl" 
                                   value="180" class="form-control">
                        </div>
                    </div>
                </div>
                
                <div class="retention-item">
                    <h5>Завершенные задачи</h5>
                    <div class="row">
                        <div class="col">
                            <label>Срок хранения (дни)</label>
                            <input type="number" id="retentionTasksTtl" 
                                   value="30" class="form-control">
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="mt-3">
                <button class="btn btn-primary" onclick="saveRetentionPolicies()">
                    <i class="fas fa-save"></i> Сохранить
                </button>
                <button class="btn btn-warning" onclick="runRetentionNow()">
                    <i class="fas fa-play"></i> Запустить сейчас
                </button>
                <button class="btn btn-info" onclick="exportArchive()">
                    <i class="fas fa-file-export"></i> Экспорт архива
                </button>
            </div>
        </div>
    </div>
    
    <div class="card mt-3">
        <div class="card-header">
            <h5>Статистика хранения</h5>
        </div>
        <div class="card-body">
            <div class="row">
                <div class="col-md-3">
                    <div class="stat-item">
                        <span class="stat-label">Аудит-события</span>
                        <span class="stat-value" id="statAuditCount">0</span>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-item">
                        <span class="stat-label">Архивные события</span>
                        <span class="stat-value" id="statArchiveCount">0</span>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-item">
                        <span class="stat-label">Находки</span>
                        <span class="stat-value" id="statFindingsCount">0</span>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="stat-item">
                        <span class="stat-label">Завершенные задачи</span>
                        <span class="stat-value" id="statTasksCount">0</span>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
✅ КРИТЕРИИ ПРИЕМКИ
Модели и БД
□ Архивные модели созданы (AuditLogArchive, FindingArchive)
□ Миграция создана и применена
□ Политики хранения загружаются из конфига
Архивация
□ Архивация аудит-событий (перемещение в архивную таблицу)
□ Архивация находок
□ Очистка архивных таблиц (по archive_ttl)
□ Очистка завершенных задач
Экспорт
□ Экспорт архивных данных в JSON
□ Экспорт архивных данных в CSV
□ Настраиваемый путь для экспорта
Задачи
□ Celery Beat задача для периодической архивации
□ Ручной запуск через API
□ Dry-run режим
API
□ GET /api/retention/policies — получение политик
□ POST /api/retention/run — ручной запуск
□ GET /api/retention/status — статус
□ POST /api/retention/export — экспорт
WebUI
□ Вкладка «Хранение данных» в настройках
□ Отображение текущих политик
□ Кнопка запуска архивации
□ Статистика хранения
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Применение миграции
alembic upgrade head

# 2. Запуск Celery worker
celery -A manager.src.workers.celery_app worker -Q retention --loglevel=info

# 3. Запуск Celery beat
celery -A manager.src.workers.celery_app beat --loglevel=info

# 4. Ручной запуск архивации
curl -X POST http://localhost:8000/api/retention/run \
  -H "Authorization: Bearer <admin-token>"

# 5. Проверка статуса
curl http://localhost:8000/api/retention/status \
  -H "Authorization: Bearer <admin-token>"

# 6. Экспорт архива
curl -X POST http://localhost:8000/api/retention/export \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"data_type":"audit","limit":1000}'
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_35_retention
git add .
git commit -m "feat: День 35 — Архивация данных

- Архивные таблицы (audit_logs_archive, findings_archive)
- Политики хранения (RetentionPolicy)
- Архивация событий (Archiver)
- Очистка данных (Cleaner)
- Экспорт в JSON/CSV (Exporter)
- Celery Beat для периодической архивации
- API эндпоинты (/api/retention/*)
- WebUI: настройки хранения данных"