📋 ТЗ: УНИФИЦИРОВАННЫЙ ФОРМАТ СОБЫТИЙ (ДЕНЬ 25)
Файл: prompts/tz/day_25_unified_event_format.md

🎯 ЦЕЛЬ
Создать единый формат событий для Windows и Linux-агентов, чтобы Manager и WebUI обрабатывали их одинаково. Унифицировать структуру данных, адаптировать агентов и обновить API.

📁 ФАЙЛЫ ДЛЯ ИЗМЕНЕНИЯ
Изменить:
text
audit-agent/collector.py          # Windows → единый формат
audit-agent-linux/collector.py    # Linux → единый формат
manager/src/db/models.py          # AuditLog → единый формат
manager/src/api/audit.py          # API → единый формат
webui/api/routes.py               # WebUI → единый формат
Создать:
text
shared/event_schema.py            # Единая Pydantic-схема
shared/__init__.py
📋 ДЕТАЛЬНОЕ ТЗ
1. Создать единую схему событий (shared/event_schema.py)
python
from typing import Optional, Dict, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class UnifiedEvent(BaseModel):
    """
    Единый формат событий для Windows и Linux-агентов
    """

    event_type: Literal["read", "write", "delete", "move", "rename"] = Field(
        ..., description="Тип события"
    )

    event_source: Literal["windows_agent", "linux_agent", "scanner"] = Field(
        ..., description="Источник события"
    )

    user: Optional[str] = Field(None, description="Пользователь, инициировавший событие")
    user_sid: Optional[str] = Field(None, description="SID пользователя (Windows)")

    file_path: str = Field(..., description="Путь к файлу")
    old_path: Optional[str] = Field(None, description="Старый путь (для move/rename)")

    source_host: Optional[str] = Field(None, description="Имя хоста-источника")

    metadata: Dict = Field(default_factory=dict, description="Дополнительные данные")

    created_at: datetime = Field(default_factory=datetime.now, description="Время события")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
2. Адаптировать Windows-агент (audit-agent/collector.py)
Изменить _normalize_event для использования UnifiedEvent:

python
from shared.event_schema import UnifiedEvent

def _normalize_event(self, raw: Dict) -> Dict:
    event_id = raw.get('event_id')
    event_type_map = {
        4656: 'read',
        4660: 'delete',
        4663: 'write',
        4670: 'write',
        5140: 'read',
        5145: 'read',
    }

    return UnifiedEvent(
        event_type=event_type_map.get(event_id, 'unknown'),
        event_source='windows_agent',
        user=raw.get('user'),
        file_path=raw.get('file_path', ''),
        old_path=raw.get('old_path'),
        source_host=raw.get('hostname'),
        metadata={'event_id': event_id, 'raw': raw},
        created_at=raw.get('timestamp') or datetime.now()
    ).dict()
3. Адаптировать Linux-агент (audit-agent-linux/collector.py)
Изменить _event_handler для использования UnifiedEvent:

python
from shared.event_schema import UnifiedEvent

def _event_handler(self, event):
    # ... существующий код ...

    audit_event = UnifiedEvent(
        event_type=event_type,
        event_source='linux_agent',
        user=user,
        file_path=event.pathname,
        old_path=old_path,
        source_host=os.uname().nodename,
        metadata={
            'event_mask': event.maskname,
            'pid': event.pid
        },
        created_at=datetime.now()
    ).dict()

    if self.callback:
        self.callback(audit_event)
4. Обновить модель AuditLog (manager/src/db/models.py)
Добавить поле event_source если его нет (уже должно быть из Дня 16). Убедиться, что метаданные хранятся как JSON.

python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    # ... существующие поля ...
    event_source = Column(String(50), default="agent")
    metadata = Column(JSON, default={})
5. Обновить API (manager/src/api/audit.py)
Изменить прием событий для работы с UnifiedEvent:

python
from shared.event_schema import UnifiedEvent

class AuditEventPayload(BaseModel):
    events: List[UnifiedEvent]

@router.post("/events")
def ingest_audit_events(
    agent_id: int,
    payload: AuditEventPayload,
    db: Session = Depends(get_db)
):
    agent = db.query(AuditAgent).filter(AuditAgent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, f"Agent {agent_id} not found")

    saved = 0
    for event in payload.events:
        audit = AuditLog(
            agent_id=agent_id,
            event_type=event.event_type,
            event_source=event.event_source,
            user=event.user,
            user_sid=event.user_sid,
            file_path=event.file_path,
            old_path=event.old_path,
            source_host=event.source_host or agent.hostname,
            metadata=event.metadata,
            created_at=event.created_at or datetime.utcnow()
        )
        db.add(audit)
        saved += 1

    agent.events_sent += saved
    agent.last_event_at = datetime.utcnow()
    db.commit()

    return {"status": "accepted", "saved": saved}
6. Обновить WebUI API (webui/api/routes.py)
Убедиться, что WebUI читает и отображает унифицированные события (изменений не требуется, если данные уже в едином формате).

7. Обновить requirements.txt
Добавить в корневой requirements.txt:

txt
pydantic>=2.0.0
✅ КРИТЕРИИ ПРИЕМКИ
□ Файл shared/event_schema.py создан
□ Windows-агент использует UnifiedEvent
□ Linux-агент использует UnifiedEvent
□ Manager API принимает UnifiedEvent
□ WebUI отображает события от обоих агентов
□ Все старые события остаются читаемыми
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запустить Manager
python -m uvicorn manager.src.main:app --port 8000

# 2. Запустить Windows-агент
cd audit-agent
python main.py

# 3. Запустить Linux-агент
cd ~/dcap-system/audit-agent-linux
./start.sh --daemon

# 4. Создать события в Windows
echo test > D:\test_audit\file.txt
del D:\test_audit\file.txt

# 5. Создать события в Linux
echo test > ~/test_audit/file.txt
rm ~/test_audit/file.txt

# 6. Проверить WebUI
# http://localhost:8001 → Аудит
# Должны быть события от обоих агентов с одинаковым форматом
📁 СТРУКТУРА ПОСЛЕ ВЫПОЛНЕНИЯ
text
dcap-system/
├── shared/
│   ├── __init__.py
│   └── event_schema.py
├── audit-agent/
│   └── collector.py           # ✅ адаптирован
├── audit-agent-linux/
│   └── collector.py           # ✅ адаптирован
├── manager/
│   └── src/
│       ├── api/audit.py       # ✅ адаптирован
│       └── db/models.py       # ✅ проверен
└── webui/
    └── api/routes.py          # ✅ проверен
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_25_unified_format
git add shared/ audit-agent/collector.py audit-agent-linux/collector.py manager/src/api/audit.py
git commit -m "feat: День 25 — унифицированный формат событий (Windows + Linux)"
Разработчик (кодер), приступай! 🚀