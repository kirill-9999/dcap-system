# manager/src/auth/dependencies.py
from fastapi import Depends, HTTPException, status, Request
from typing import List, Optional

from .models import User


def get_current_user(request: Request) -> Optional[User]:
    """Получение текущего пользователя из request.state (устанавливается middleware)."""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user


def require_auth(current_user: User = Depends(get_current_user)) -> User:
    """Требовать аутентификацию."""
    return current_user


def require_roles(roles: List[str]):
    """Декоратор для проверки ролей."""
    async def role_checker(current_user: User = Depends(require_auth)):
        user_roles = [role.name for role in current_user.roles]
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required roles: {', '.join(roles)}"
            )
        return current_user
    return role_checker


# Упрощенные зависимости
require_admin = require_roles(["admin"])
require_viewer = require_roles(["admin", "viewer", "auditor", "scanner"])
require_auditor = require_roles(["admin", "auditor"])
require_scanner = require_roles(["admin", "scanner"])
