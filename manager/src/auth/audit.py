# manager/src/auth/audit.py
"""Аудит аутентификации и управления пользователями.

BUG-095 (TASK-061/062, v3.13.24): события `auth_login`, `auth_failed`,
`auth_logout`, `user_created`, `user_updated`, `user_deleted`,
`user_password_changed`, `role_assigned`, `role_revoked` не писались в
`audit_logs` — требования 152-ФЗ / GDPR / PCI DSS 10.2.x не выполнялись
(невозможно установить, кто и когда входил в систему и менял права).

Решения по открытым вопросам ТЗ:
  * `auth_refresh` НЕ пишется — refresh каждые 15 мин создаёт шум
    (рекомендация архитектора из ТЗ);
  * `auth_failed` пишется в общую `audit_logs` (единая точка для SIEM);
  * retention — по общим правилам таблицы `audit_logs`;
  * rate-limit-алерт на N неудачных попыток — отдельная задача v3.1.0
    (TASK-063 отложен);
  * `file_path` = точный URL эндпоинта (`request.url.path`).

БЕЗОПАСНОСТЬ: в `metadata_json` никогда не пишутся пароли, хеши паролей,
токены и секреты — `_sanitize()` вырезает такие ключи рекурсивно.
"""
import logging
from datetime import datetime
from typing import Any, Optional, Union

from fastapi import Request
from sqlalchemy.orm import Session

from manager.src.db.models import AuditLog

logger = logging.getLogger(__name__)

# Подстроки в имени ключа, при которых значение вырезается из metadata
_FORBIDDEN_KEY_PARTS = ("password", "passwd", "token", "secret", "hash", "salt", "credential")

UserLike = Union[str, None, Any]


def _sanitize(value: Any) -> Any:
    """Рекурсивно вырезает из metadata ключи с паролями/токенами/секретами."""
    if isinstance(value, dict):
        clean = {}
        for key, val in value.items():
            key_str = str(key).lower()
            if any(part in key_str for part in _FORBIDDEN_KEY_PARTS):
                continue
            clean[key] = _sanitize(val)
        return clean
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


def _user_name(user: UserLike) -> Optional[str]:
    """Логин пользователя: строка или ORM-объект User."""
    if user is None:
        return None
    if isinstance(user, str):
        return user or None
    return getattr(user, "username", None)


def _user_sid(user: UserLike) -> Optional[str]:
    """SID/DOMAIN\\username для AD-пользователей."""
    if user is None or isinstance(user, str):
        return None
    return getattr(user, "domain_user", None)


def log_auth_event(
    db: Session,
    event_type: str,
    user: UserLike = None,
    request: Optional[Request] = None,
    metadata: Optional[dict] = None,
    path: Optional[str] = None,
) -> Optional[AuditLog]:
    """Записать событие аутентификации/управления пользователями в `audit_logs`.

    Никогда не бросает исключений: сбой аудита не должен ломать аутентификацию
    (fail-open с записью в лог Manager).

    Args:
        db: SQLAlchemy-сессия.
        event_type: `auth_login` / `auth_failed` / `auth_logout` / `user_created`
            / `user_updated` / `user_deleted` / `user_password_changed`
            / `role_assigned` / `role_revoked`.
        user: ORM `User`, строка-логин (для неудачных попыток) или None.
        request: FastAPI Request (для `file_path` и IP источника).
        metadata: дополнительные поля; пароли/токены вырезаются автоматически.
        path: явный `file_path`, если request недоступен.

    Returns:
        Созданный `AuditLog` или None при ошибке записи.
    """
    file_path = path
    source_host = None
    if request is not None:
        try:
            file_path = file_path or request.url.path
            source_host = request.client.host if request.client else None
        except Exception:  # noqa: BLE001 — request может быть частичным в тестах
            pass
    file_path = file_path or "/api/auth"

    try:
        log = AuditLog(
            event_type=event_type,
            event_source="api",
            user=_user_name(user),
            user_sid=_user_sid(user),
            file_path=file_path,
            source_host=source_host,
            metadata_json=_sanitize(metadata or {}),
            created_at=datetime.utcnow(),
        )
        db.add(log)
        db.commit()
        return log
    except Exception as e:  # noqa: BLE001
        logger.warning("Failed to log auth event %s: %s", event_type, e)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def classify_login_failure(db: Session, username: Optional[str]) -> str:
    """Причина неудачного входа: user_not_found / user_inactive / invalid_credentials.

    Только для аудита — HTTP-ответ остаётся общим «Invalid credentials»,
    чтобы не перечислять существующие учётки.
    """
    from .models import User

    if not username:
        return "invalid_credentials"
    try:
        user = db.query(User).filter(User.username == username).first()
    except Exception as e:  # noqa: BLE001
        logger.warning("classify_login_failure query failed: %s", e)
        return "invalid_credentials"
    if not user:
        return "user_not_found"
    if not user.is_active:
        return "user_inactive"
    return "invalid_credentials"


def role_diff(before: list, after: list) -> tuple:
    """Разница списков ролей: (назначенные, снятые)."""
    before_set = set(before or [])
    after_set = set(after or [])
    return sorted(after_set - before_set), sorted(before_set - after_set)
