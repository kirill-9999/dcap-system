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

router = APIRouter(tags=["audit"])


class AuditEventPayload(BaseModel):
    event_type: str          # read, write, delete, move, rename
    event_source: Optional[str] = "agent"  # windows_agent, linux_agent, scanner
    user: Optional[str] = None
    user_sid: Optional[str] = None
    file_path: str
    old_path: Optional[str] = None
    source_host: Optional[str] = None
    metadata: Optional[Dict] = {}
    created_at: Optional[str] = None   # ISO формат


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


@router.post("/api/audit/agents/register")
def register_agent(
    payload: RegisterAgentRequest,
    db: Session = Depends(get_db)
):
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
        last_heartbeat=datetime.utcnow()
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    # TODO: генерация API key (будет в День 35-37)
    return {"status": "registered", "agent_id": agent.id}


@router.post("/api/audit/agents/heartbeat")
def agent_heartbeat(
    payload: HeartbeatRequest,
    db: Session = Depends(get_db)
):
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


@router.post("/api/audit/events")
def ingest_audit_events(
    payload: IngestEventsRequest,
    db: Session = Depends(get_db)
):
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
            created_at=event.created_at and datetime.fromisoformat(event.created_at) or datetime.utcnow()
        )
        db.add(audit)
        saved += 1

    agent.events_sent += saved
    agent.last_event_at = datetime.utcnow()
    db.commit()

    return {"status": "accepted", "saved": saved}


@router.get("/api/audit")
def get_audit_events(
    agent_id: Optional[int] = None,
    user: Optional[str] = None,
    event_type: Optional[str] = None,
    file_path: Optional[str] = None,
    since: Optional[str] = None,   # ISO формат
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Получить аудит-события с фильтрацией"""
    query = db.query(models.AuditLog)

    if agent_id:
        query = query.filter(models.AuditLog.agent_id == agent_id)
    if user:
        query = query.filter(models.AuditLog.user.ilike(f"%{user}%"))
    if event_type:
        query = query.filter(models.AuditLog.event_type == event_type)
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
        ]
    }


@router.get("/api/audit/stats")
def get_audit_stats(
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """Статистика по аудиту за N дней"""
    since = datetime.utcnow() - timedelta(days=days)

    from sqlalchemy import func

    total = db.query(models.AuditLog).filter(models.AuditLog.created_at >= since).count()

    type_stats = db.query(
        models.AuditLog.event_type,
        func.count(models.AuditLog.id).label('count')
    ).filter(models.AuditLog.created_at >= since)\
     .group_by(models.AuditLog.event_type).all()

    user_stats = db.query(
        models.AuditLog.user,
        func.count(models.AuditLog.id).label('count')
    ).filter(models.AuditLog.created_at >= since)\
     .filter(models.AuditLog.user.isnot(None))\
     .group_by(models.AuditLog.user)\
     .order_by(func.count(models.AuditLog.id).desc())\
     .limit(10).all()

    return {
        "total": total,
        "days": days,
        "by_type": [{"type": s[0], "count": s[1]} for s in type_stats],
        "top_users": [{"user": s[0], "count": s[1]} for s in user_stats]
    }
