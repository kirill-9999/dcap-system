"""
API для системы аудита DCAP

Эндпоинты:
- POST /api/audit/agents/register — регистрация агента аудита
- POST /api/audit/agents/heartbeat — heartbeat агента
- POST /api/audit/events — приём событий от агента
- GET /api/audit — просмотр аудит-событий (для WebUI)
- GET /api/audit/stats — статистика по аудиту
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
from datetime import datetime, timedelta

from manager.src.db.session import get_db
from manager.src.db import models
from manager.src.auth.dependencies import require_admin
from manager.src.auth.models import User

router = APIRouter(tags=["audit"])

STALE_THRESHOLD_MINUTES = 2


def _mark_stale_agents(db: Session):
    """Пометить агентов как offline, если heartbeat старше порога."""
    threshold = datetime.utcnow() - timedelta(minutes=STALE_THRESHOLD_MINUTES)
    stale = (
        db.query(models.AuditAgent)
        .filter(models.AuditAgent.status == "online", models.AuditAgent.last_heartbeat < threshold)
        .all()
    )
    for agent in stale:
        agent.status = "offline"
    if stale:
        db.commit()


class AuditEventPayload(BaseModel):
    event_type: str  # read, write, delete, move, rename
    event_source: Optional[str] = "agent"  # windows_agent, linux_agent, scanner
    user: Optional[str] = None
    user_sid: Optional[str] = None
    file_path: str
    old_path: Optional[str] = None
    source_host: Optional[str] = None
    metadata: Optional[Dict] = {}
    created_at: Optional[str] = None  # ISO формат


class RegisterAgentRequest(BaseModel):
    name: str
    hostname: str
    ip_address: Optional[str] = None
    version: str = "1.0.0"


class HeartbeatRequest(BaseModel):
    agent_id: int
    status: str = "online"
    stats: Optional[Dict] = None
    error: Optional[str] = None


class IngestEventsRequest(BaseModel):
    agent_id: int
    events: List[AuditEventPayload]


class PermissionEntryPayload(BaseModel):
    resource_path: str
    principal_type: str = "user"  # user, group, local_user, ad_user, ad_group, system
    principal_name: str
    principal_sid: Optional[str] = None
    principal_domain: Optional[str] = None
    permission_type: Optional[str] = None  # read, write, delete, modify, full_control
    permission_source: Optional[str] = "direct"
    is_inherited: bool = False
    inherited_from: Optional[str] = None
    permissions: Optional[List[str]] = None  # alternative: список прав


class IngestPermissionsRequest(BaseModel):
    agent_id: int
    agent_type: Optional[str] = "agent"
    permissions: List[PermissionEntryPayload]
    collected_at: Optional[str] = None


@router.post("/api/audit/agents/register")
def register_agent(payload: RegisterAgentRequest, db: Session = Depends(get_db)):
    """
    Регистрация нового агента аудита.
    Если агент с таким именем уже существует — обновляет heartbeat и возвращает существующий id.
    """
    name = payload.name
    hostname = payload.hostname
    ip_address = payload.ip_address
    version = payload.version

    existing = db.query(models.AuditAgent).filter(models.AuditAgent.name == name).first()
    if existing:
        existing.last_heartbeat = datetime.utcnow()
        existing.hostname = hostname
        existing.ip_address = ip_address or existing.ip_address
        existing.version = version
        existing.status = "online"
        db.commit()
        return {"status": "updated", "agent_id": existing.id}

    agent = models.AuditAgent(
        name=name,
        hostname=hostname,
        ip_address=ip_address,
        version=version,
        status="online",
        last_heartbeat=datetime.utcnow(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # TODO: генерация API key (будет в День 35-37)
    return {"status": "registered", "agent_id": agent.id}


@router.post("/api/audit/agents/heartbeat")
def agent_heartbeat(payload: HeartbeatRequest, db: Session = Depends(get_db)):
    """Обновление статуса агента"""
    agent_id = payload.agent_id
    status = payload.status
    stats = payload.stats
    error = payload.error

    agent = db.query(models.AuditAgent).filter(models.AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    agent.last_heartbeat = datetime.utcnow()
    agent.status = status

    if error:
        agent.last_error = error[:500]

    if stats:
        agent.events_sent = stats.get("events_sent", agent.events_sent)
        agent.events_failed = stats.get("events_failed", agent.events_failed)
        if stats.get("last_event_at"):
            agent.last_event_at = datetime.fromisoformat(stats["last_event_at"])

    db.commit()
    return {"status": "ok"}


@router.get("/api/audit/agents")
def list_audit_agents(db: Session = Depends(get_db)):
    """Список агентов аудита с актуальным статусом"""
    _mark_stale_agents(db)

    agents = db.query(models.AuditAgent).order_by(models.AuditAgent.id).all()
    total = len(agents)
    online = sum(1 for a in agents if a.status == "online")
    offline = sum(1 for a in agents if a.status == "offline")
    error = sum(1 for a in agents if a.status == "error")

    return {
        "total": total,
        "online": online,
        "offline": offline,
        "error": error,
        "agents": [
            {
                "id": a.id,
                "name": a.name,
                "hostname": a.hostname,
                "status": a.status,
                "last_heartbeat": a.last_heartbeat.isoformat() if a.last_heartbeat else None,
                "events_sent": a.events_sent,
                "registered_at": a.registered_at.isoformat() if a.registered_at else None,
                "version": getattr(a, "version", None),
            }
            for a in agents
        ],
    }


@router.post("/api/audit/events")
def ingest_audit_events(payload: IngestEventsRequest, db: Session = Depends(get_db)):
    """Принять события от агента"""
    agent_id = payload.agent_id
    events = payload.events

    agent = db.query(models.AuditAgent).filter(models.AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    saved = 0
    for event in events:
        audit = models.AuditLog(
            agent_id=agent_id,
            event_type=event.event_type,
            event_source=event.event_source or "agent",
            user=event.user,
            user_sid=event.user_sid,
            file_path=event.file_path,
            old_path=event.old_path,
            source_host=event.source_host or agent.hostname,
            metadata_json=event.metadata or {},
            created_at=event.created_at
            and datetime.fromisoformat(event.created_at)
            or datetime.utcnow(),
        )
        db.add(audit)
        saved += 1

    agent.events_sent += saved
    agent.last_event_at = datetime.utcnow()
    db.commit()

    return {"status": "accepted", "saved": saved}


@router.post("/api/audit/permissions")
def ingest_audit_permissions(payload: IngestPermissionsRequest, db: Session = Depends(get_db)):
    """Принять права доступа от агента (POST /api/audit/permissions).

    Ищет/создаёт ресурс по пути и обновляет записи AccessEntry.
    Существующие активные записи по ресурсу+субъекту+правам помечаются как неактивные
    перед записью новой коллекции (простая инкрементальная схема).
    """
    agent_id = payload.agent_id
    agent = db.query(models.AuditAgent).filter(models.AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    saved = 0
    skipped = 0
    for entry in payload.permissions:
        resource = (
            db.query(models.Resource).filter(models.Resource.path == entry.resource_path).first()
        )
        if not resource:
            resource = models.Resource(path=entry.resource_path, type="FILESYSTEM")
            db.add(resource)
            db.flush()

        # Права: одно значение permission_type или список permissions
        perm_type = None
        if entry.permission_type:
            perm_type = entry.permission_type.lower()
        elif entry.permissions:
            perm_type = ",".join(str(p).lower() for p in entry.permissions)

        if not perm_type:
            skipped += 1
            continue

        db.add(
            models.AccessEntry(
                resource_id=resource.id,
                principal_type=entry.principal_type,
                principal_name=entry.principal_name,
                principal_sid=entry.principal_sid,
                principal_domain=entry.principal_domain,
                permission_type=perm_type,
                permission_source=entry.permission_source or "direct",
                inherited_from=entry.inherited_from,
                is_inherited=entry.is_inherited,
                granted_by=agent.name,
                last_verified_at=datetime.utcnow(),
                collector_source=payload.agent_type or "agent",
            )
        )
        saved += 1

    db.commit()
    return {"status": "accepted", "saved": saved, "skipped": skipped}


@router.get("/api/audit")
def get_audit_events(
    agent_id: Optional[int] = None,
    user: Optional[str] = None,
    event_type: Optional[str] = None,
    # BUG-091 (TASK-058, v3.13.22): WebUI шлёт event_source (выпадающий список
    # «Источник» на странице Аудита), а параметр не поддерживался — фильтр
    # молча игнорировался и список не менялся.
    event_source: Optional[str] = None,
    file_path: Optional[str] = None,
    since: Optional[str] = None,  # ISO формат
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Получить аудит-события с фильтрацией"""
    query = db.query(models.AuditLog)

    if agent_id:
        query = query.filter(models.AuditLog.agent_id == agent_id)
    if user:
        query = query.filter(models.AuditLog.user.ilike(f"%{user}%"))
    if event_type:
        query = query.filter(models.AuditLog.event_type == event_type)
    if event_source:
        query = query.filter(models.AuditLog.event_source == event_source)
    if file_path:
        query = query.filter(models.AuditLog.file_path.ilike(f"%{file_path}%"))
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(models.AuditLog.created_at >= since_dt)
        except:
            pass

    total = query.count()
    events = query.order_by(models.AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_source": e.event_source,
                "user": e.user,
                "file_path": e.file_path,
                "old_path": e.old_path,
                "source_host": e.source_host,
                "metadata": e.metadata_json,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    }


@router.get("/api/audit/stats")
def get_audit_stats(days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    """Статистика по аудиту за N дней"""
    since = datetime.utcnow() - timedelta(days=days)

    from sqlalchemy import func

    total = db.query(models.AuditLog).filter(models.AuditLog.created_at >= since).count()

    type_stats = (
        db.query(models.AuditLog.event_type, func.count(models.AuditLog.id).label("count"))
        .filter(models.AuditLog.created_at >= since)
        .group_by(models.AuditLog.event_type)
        .all()
    )

    user_stats = (
        db.query(models.AuditLog.user, func.count(models.AuditLog.id).label("count"))
        .filter(models.AuditLog.created_at >= since)
        .filter(models.AuditLog.user.isnot(None))
        .group_by(models.AuditLog.user)
        .order_by(func.count(models.AuditLog.id).desc())
        .limit(10)
        .all()
    )

    source_stats = (
        db.query(models.AuditLog.event_source, func.count(models.AuditLog.id).label("count"))
        .filter(models.AuditLog.created_at >= since)
        .filter(models.AuditLog.event_source.isnot(None))
        .group_by(models.AuditLog.event_source)
        .order_by(func.count(models.AuditLog.id).desc())
        .all()
    )

    agents_online = db.query(models.AuditAgent).filter(models.AuditAgent.status == "online").count()
    agents_total = db.query(models.AuditAgent).count()

    return {
        "total": total,
        "days": days,
        "by_type": [{"type": s[0], "count": s[1]} for s in type_stats],
        "top_users": [{"user": s[0], "count": s[1]} for s in user_stats],
        "by_source": [{"source": s[0], "count": s[1]} for s in source_stats],
        "agents_total": agents_total,
        "agents_online": agents_online,
    }


@router.delete("/api/audit/agents/{agent_id}")
def delete_audit_agent(
    agent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """Удалить агент аудита. Связанные события остаются (agent_id = NULL). Только Admin (BUG-055)."""
    agent = db.query(models.AuditAgent).filter(models.AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    db.query(models.AuditLog).filter(models.AuditLog.agent_id == agent_id).update(
        {"agent_id": None}
    )
    db.delete(agent)
    db.commit()

    return {"status": "deleted", "agent_id": agent_id}
