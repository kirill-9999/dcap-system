📋 ТЗ: МОДЕЛЬ AUDITLOG И АРХИТЕКТУРА АГЕНТА (ДЕНЬ 16) — СКОРРЕКТИРОВАННОЕ
Файл: prompts/tz/day_16_auditlog.md

🎯 ЦЕЛЬ
Создать фундамент для системы аудита в DCAP:

Модели данных для хранения аудит-событий и информации об агентах

API для регистрации, heartbeat и приема событий от агентов

Базовую структуру легкого агента для сбора событий с файловых серверов

Важно: Отладка ведется на Windows 10 Home. Настройка аудита выполняется через auditpol и SACL на папках (без secpol.msc).

📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ/ИЗМЕНЕНИЯ
Изменить:
text
manager/src/db/models.py          # Добавить AuditLog, AuditAgent
manager/src/api/audit.py          # Создать API для агентов и аудита
Создать:
text
manager/src/connectors/audit/windows_audit.py   # Чтение Security Log (wevtutil)
manager/src/connectors/audit/__init__.py
Подключить:
text
manager/src/main.py               # Подключить роутер audit
📋 ДЕТАЛЬНОЕ ТЗ
1. Модели данных (в models.py)
1.1. Модель AuditAgent
python
class AuditAgent(Base):
    __tablename__ = "audit_agents"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)   # например: server01-audit
    hostname = Column(String(200), nullable=False)
    ip_address = Column(String(45), nullable=True)
    status = Column(String(20), default="offline")   # offline, online, error, updating

    version = Column(String(20), default="1.0.0")

    # Конфигурация агента (передается из Manager)
    config = Column(JSON, default={
        "read_interval": 60,          # секунд между чтением Security Log
        "batch_size": 100,            # сколько событий за раз
        "buffer_size": 10000,         # сколько хранить локально при потере связи
        "event_filters": [],          # список Event ID для сбора
        "paths": []                   # какие папки аудировать (SACL)
    })

    # Мониторинг
    last_heartbeat = Column(DateTime, nullable=True)
    registered_at = Column(DateTime, default=datetime.utcnow)
    last_error = Column(Text, nullable=True)

    # Статистика
    events_sent = Column(Integer, default=0)
    events_failed = Column(Integer, default=0)
    last_event_at = Column(DateTime, nullable=True)

    # Связи
    audit_logs = relationship("AuditLog", back_populates="agent")
1.2. Модель AuditLog
python
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    agent_id = Column(Integer, ForeignKey("audit_agents.id"), nullable=True, index=True)

    event_type = Column(String(50), nullable=False)      # read, write, delete, move, rename
    event_source = Column(String(50), default="agent")   # agent, scanner, api, system
    user = Column(String(200), nullable=True)
    user_sid = Column(String(100), nullable=True)
    file_path = Column(String(500), nullable=False)
    old_path = Column(String(500), nullable=True)        # для move/rename
    source_host = Column(String(100), nullable=True)     # откуда пришло событие

    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связи
    agent = relationship("AuditAgent", back_populates="audit_logs")
Добавить в AuditAgent:

python
audit_logs = relationship("AuditLog", back_populates="agent", cascade="all, delete-orphan")
2. API для управления агентами (manager/src/api/audit.py)
2.1. Регистрация агента
python
@router.post("/api/audit/agents/register")
def register_agent(
    name: str,
    hostname: str,
    ip_address: Optional[str] = None,
    version: str = "1.0.0",
    db: Session = Depends(get_db)
):
    """
    Регистрация нового агента аудита.
    Если агент с таким именем уже существует — обновляет heartbeat и возвращает существующий id.
    """
    existing = db.query(AuditAgent).filter(AuditAgent.name == name).first()
    if existing:
        existing.last_heartbeat = datetime.utcnow()
        existing.hostname = hostname
        existing.ip_address = ip_address or existing.ip_address
        existing.version = version
        existing.status = "online"
        db.commit()
        return {"status": "updated", "agent_id": existing.id}

    agent = AuditAgent(
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
2.2. Heartbeat агента
python
@router.post("/api/audit/agents/heartbeat")
def agent_heartbeat(
    agent_id: int,
    status: str = "online",
    stats: Optional[Dict] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Обновление статуса агента"""
    agent = db.query(AuditAgent).filter(AuditAgent.id == agent_id).first()
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
2.3. Прием событий от агента
python
class AuditEventPayload(BaseModel):
    event_type: str          # read, write, delete, move, rename
    user: Optional[str] = None
    user_sid: Optional[str] = None
    file_path: str
    old_path: Optional[str] = None
    metadata: Optional[Dict] = {}
    created_at: Optional[str] = None   # ISO формат

@router.post("/api/audit/events")
def ingest_audit_events(
    agent_id: int,
    events: List[AuditEventPayload],
    db: Session = Depends(get_db)
):
    """Принять события от агента"""
    agent = db.query(AuditAgent).filter(AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    saved = 0
    for event in events:
        audit = AuditLog(
            agent_id=agent_id,
            event_type=event.event_type,
            event_source="agent",
            user=event.user,
            user_sid=event.user_sid,
            file_path=event.file_path,
            old_path=event.old_path,
            source_host=agent.hostname,
            metadata=event.metadata or {},
            created_at=event.created_at and datetime.fromisoformat(event.created_at) or datetime.utcnow()
        )
        db.add(audit)
        saved += 1

    agent.events_sent += saved
    agent.last_event_at = datetime.utcnow()
    db.commit()

    return {"status": "accepted", "saved": saved}
2.4. Просмотр аудит-событий (для WebUI)
python
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
    query = db.query(AuditLog)

    if agent_id:
        query = query.filter(AuditLog.agent_id == agent_id)
    if user:
        query = query.filter(AuditLog.user.ilike(f"%{user}%"))
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if file_path:
        query = query.filter(AuditLog.file_path.ilike(f"%{file_path}%"))
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(AuditLog.created_at >= since_dt)
        except:
            pass

    total = query.count()
    events = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "user": e.user,
                "file_path": e.file_path,
                "old_path": e.old_path,
                "source_host": e.source_host,
                "metadata": e.metadata,
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

    total = db.query(AuditLog).filter(AuditLog.created_at >= since).count()

    type_stats = db.query(
        AuditLog.event_type,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .group_by(AuditLog.event_type).all()

    user_stats = db.query(
        AuditLog.user,
        func.count(AuditLog.id).label('count')
    ).filter(AuditLog.created_at >= since)\
     .filter(AuditLog.user.isnot(None))\
     .group_by(AuditLog.user)\
     .order_by(func.count(AuditLog.id).desc())\
     .limit(10).all()

    return {
        "total": total,
        "days": days,
        "by_type": [{"type": s[0], "count": s[1]} for s in type_stats],
        "top_users": [{"user": s[0], "count": s[1]} for s in user_stats]
    }
3. Чтение Security Log (windows_audit.py)
Создать manager/src/connectors/audit/windows_audit.py:

python
"""
Сбор событий файловой системы Windows через wevtutil.
Работает на Windows 10 Home/Pro/Server.
"""

import subprocess
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class WindowsAuditCollector:
    """Чтение Security Log через wevtutil"""

    def __init__(self):
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        try:
            subprocess.run(['wevtutil', '--help'], capture_output=True, timeout=5)
            return True
        except:
            return False

    def collect_events(self, since: Optional[datetime] = None,
                       event_ids: Optional[List[int]] = None,
                       limit: int = 1000) -> List[Dict]:
        """
        Собрать события из Security Log

        Аргументы:
            since: собирать события с указанного времени
            event_ids: список Event ID для фильтрации
            limit: максимум событий

        Возвращает:
            List[Dict]: список событий
        """
        if not self._available:
            return []

        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)

        if event_ids is None:
            event_ids = [4656, 4660, 4663, 4670, 5140, 5145]

        time_filter = since.strftime("%Y-%m-%dT%H:%M:%S")
        query = f"*[System[TimeCreated[@SystemTime>='{time_filter}']]]"

        try:
            result = subprocess.run(
                ['wevtutil', 'qe', 'Security',
                 '/q', query,
                 '/e', 'Events',
                 '/f', 'Text',
                 '/c', str(limit)],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=30
            )
            return self._parse_events(result.stdout, event_ids)
        except Exception as e:
            print(f"[Audit] Ошибка сбора событий: {e}")
            return []

    def _parse_events(self, output: str, event_ids: List[int]) -> List[Dict]:
        """Парсинг вывода wevtutil"""
        events = []
        current = {}
        in_event = False

        for line in output.split('\n'):
            line = line.strip()

            if line.startswith('Event['):
                if current and in_event:
                    events.append(current)
                    current = {}
                in_event = True
                continue

            if not in_event:
                continue

            if line.startswith('EventId:'):
                try:
                    eid = int(line.split(':', 1)[1].strip())
                    if eid not in event_ids:
                        in_event = False
                        current = {}
                        continue
                    current['event_id'] = eid
                except:
                    pass

            elif line.startswith('TimeCreated:'):
                current['timestamp'] = line.split(':', 1)[1].strip()

            elif 'SubjectUserName:' in line:
                current['user'] = line.split(':', 1)[1].strip()

            elif 'ObjectName:' in line:
                current['file_path'] = line.split(':', 1)[1].strip()

            elif 'AccessMask:' in line:
                current['access_mask'] = line.split(':', 1)[1].strip()

            elif 'OldPath:' in line:
                current['old_path'] = line.split(':', 1)[1].strip()

            elif 'NewPath:' in line:
                current['new_path'] = line.split(':', 1)[1].strip()

        if current and in_event:
            events.append(current)

        return events

    def map_event_to_audit(self, raw: Dict) -> Dict:
        """Преобразовать raw-событие в формат AuditLog"""
        event_id = raw.get('event_id')
        event_type = self._map_event_type(event_id)

        return {
            'event_type': event_type,
            'user': raw.get('user'),
            'file_path': raw.get('file_path', ''),
            'old_path': raw.get('old_path'),
            'metadata': {
                'event_id': event_id,
                'access_mask': raw.get('access_mask')
            },
            'created_at': self._parse_timestamp(raw.get('timestamp'))
        }

    def _map_event_type(self, event_id: int) -> str:
        mapping = {
            4656: 'read',
            4660: 'delete',
            4663: 'write',
            4670: 'write',
            5140: 'read',
            5145: 'read',
        }
        return mapping.get(event_id, 'unknown')

    def _parse_timestamp(self, ts: str) -> Optional[datetime]:
        if not ts:
            return None
        try:
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except:
            return None
4. Подключение в main.py
python
from manager.src.api.audit import router as audit_router

app.include_router(audit_router)
✅ КРИТЕРИИ ПРИЕМКИ
□ Модели AuditAgent и AuditLog добавлены в models.py
□ init_db.py создает таблицы audit_agents и audit_logs
□ API регистрации агента работает (POST /api/audit/agents/register)
□ API heartbeat работает (POST /api/audit/agents/heartbeat)
□ API приема событий работает (POST /api/audit/events)
□ API просмотра событий работает (GET /api/audit)
□ WindowsAuditCollector читает Security Log через wevtutil
□ На Windows 10 Home аудит настраивается через auditpol + SACL (инструкция приложена)
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
powershell
# 1. Настроить аудит на тестовой папке (Windows 10 Home)
#    - Создать папку D:\test_audit
#    - В свойствах → Безопасность → Дополнительно → Аудит
#    - Добавить правило для "Everyone" на "Создание файлов", "Удаление"

# 2. Включить политику аудита (от имени администратора)
auditpol /set /subcategory:"File System" /success:enable /failure:enable

# 3. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 4. Зарегистрировать агента (ручной тест)
curl -X POST http://localhost:8000/api/audit/agents/register \
  -H "Content-Type: application/json" \
  -d '{"name":"test-agent","hostname":"DESKTOP-ABC"}'

# 5. Отправить тестовое событие
curl -X POST http://localhost:8000/api/audit/events \
  -H "Content-Type: application/json" \
  -d '{"agent_id":1,"events":[{"event_type":"read","user":"test","file_path":"D:\\test.txt"}]}'

# 6. Проверить сохранение
curl http://localhost:8000/api/audit?limit=10
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
dcap-system/
├── manager/
│   └── src/
│       ├── db/models.py              # ✅ + AuditAgent, AuditLog
│       ├── api/audit.py              # ✅ создан
│       ├── connectors/audit/
│       │   ├── __init__.py
│       │   └── windows_audit.py      # ✅ создан
│       └── main.py                   # ✅ + audit_router
├── prompts/
│   └── tz/day_16_auditlog.md         # ✅ это ТЗ
└── test_files/
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_16_auditlog
git add manager/src/db/models.py manager/src/api/audit.py manager/src/connectors/audit/
git commit -m "feat: День 16 — модель AuditLog и архитектура агента аудита"
Разработчик (кодер), приступай! 🚀