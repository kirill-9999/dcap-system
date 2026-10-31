# manager/src/api/audit_helper.py
"""Единый помощник записи аудита (BUG-202, v3.13.39).

Проблема: раньше бизнес-изменение и аудит-запись писались в сессию по-разному
(log_auth_event — с собственным commit; логи в findings.py — отдельными
commit'ами). При откате транзакции (rollback) аудит мог остаться в БД, а
изменение — нет, и наоборот — это нарушает целостность журнала 152-ФЗ / PCI DSS.

`with_audit` коммитит бизнес-изменение и аудит-запись одной транзакцией:
если тело блока бросает исключение — вся транзакция откатывается целиком,
записи аудита не остаётся.
"""
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from manager.src.auth.audit import _sanitize
from manager.src.db.models import AuditLog


def _log_audit(
    db: Session,
    event_type: str,
    request: Optional[Request] = None,
    user: Any = None,
    file_path: Optional[str] = None,
    source_host: Optional[str] = None,
    metadata: Optional[dict] = None,
    created_at: Optional[datetime] = None,
) -> AuditLog:
    """Добавляет AuditLog в текущую сессию БЕЗ commit (коммитит with_audit).

    user — ORM-объект с .username или строка-логин. Секреты в metadata
    вырезаются тем же _sanitize(), что и для auth-событий.
    """
    username = getattr(user, "username", None)
    if username is None and isinstance(user, str):
        username = user

    if file_path is None and request is not None:
        try:
            file_path = request.url.path
        except Exception:  # noqa: BLE001 — request может быть частичным в тестах
            file_path = "/api"
    if source_host is None and request is not None:
        try:
            source_host = request.client.host if request.client else None
        except Exception:  # noqa: BLE001
            source_host = None

    log = AuditLog(
        event_type=event_type,
        event_source="api",
        user=username,
        file_path=file_path or "/api",
        source_host=source_host,
        metadata_json=_sanitize(metadata or {}),
        created_at=created_at or datetime.utcnow(),
    )
    db.add(log)
    return log


@contextmanager
def with_audit(db: Session, event_type: str, **kwargs):
    """Контекст-менеджер: бизнес-изменение + аудит = одна транзакция (BUG-202).

    ```
    meta = {"action": "role_created", "role_name": role.name}
    with with_audit(db, "role_created", user=admin, request=request, metadata=meta):
        db.add(role)
        db.flush()
        meta["role_id"] = role.id      # dict мутируется — попадёт в аудит
    ```

    Если тело блока бросает исключение — `db.rollback()` и исключение
    пробрасывается наружу: ни изменения, ни аудита в БД не остаётся.
    """
    try:
        yield
        _log_audit(db, event_type=event_type, **kwargs)
        db.commit()
    except Exception:
        db.rollback()
        raise