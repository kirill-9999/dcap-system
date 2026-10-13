# manager/src/auth/router.py
import os

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import Optional

from manager.src.db.session import get_db

from .models import User, Role
from .dependencies import get_current_user, require_admin, require_auth
from .schemas import (
    LoginRequest,
    LoginResponse,
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
    UserRoleUpdate,
    UserListResponse,
    RoleCreate,
    RoleUpdate,
    RoleResponse,
    RoleListResponse,
    ChangePasswordRequest,
)
from .manager import AuthManager
from .audit import classify_login_failure, log_auth_event, role_diff
from .rate_limit import login_limiter
from ..api.audit_helper import with_audit

router = APIRouter(prefix="/api/auth", tags=["auth"])

# BUG-168 (v3.13.39): системные роли нельзя переименовывать и менять AD-group.
SYSTEM_ROLES = {"admin", "auditor", "scanner", "viewer"}

# Регистр глобального AuthManager (заполняется в main.py при старте)
_auth_manager: AuthManager = None  # type: ignore


def set_auth_manager(am: AuthManager) -> None:
    global _auth_manager
    _auth_manager = am


def get_auth_manager() -> AuthManager:
    if _auth_manager is None:
        raise HTTPException(500, "AuthManager is not initialized")
    return _auth_manager


def cookie_secure() -> bool:
    """Secure-флаг для HttpOnly cookie (BUG-042).

    Управляется env AUTH_COOKIE_SECURE (по умолчанию False — dev на
    127.0.0.1; в production за HTTPS — ставить true). Внимание: True с
    Secure-кукой на HTTP-сайте сделает cookie невидимой браузеру.
    """
    return os.getenv("AUTH_COOKIE_SECURE", "false").lower() in ("1", "true", "yes")


# ===== ПУБЛИЧНЫЕ ЭНДПОИНТЫ =====


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    """Аутентификация пользователя (JWT)."""
    client_ip = request.client.host if request.client else "unknown"
    login_limiter.check(f"login:{client_ip}")

    user, method = await auth_manager.authenticate(
        request, db, login_data.username, login_data.password
    )

    if not user:
        # BUG-095 (TASK-061): неудачная попытка входа. Пароль/хеш не пишутся.
        log_auth_event(
            db,
            "auth_failed",
            login_data.username,
            request,
            metadata={
                "action": "login_failed",
                "reason": classify_login_failure(db, login_data.username),
                "attempted_username": login_data.username,
                "auth_mode": auth_manager.get_current_mode(),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token_data = {"user_id": user.id, "username": user.username}
    access_token = auth_manager.jwt.create_access_token(token_data)
    refresh_token = auth_manager.jwt.create_refresh_token(token_data)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure(),  # BUG-042: env AUTH_COOKIE_SECURE
        samesite="lax",
        max_age=60 * 60 * 24,  # 24 часа
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=cookie_secure(),  # BUG-042
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 дней
    )

    # BUG-095 (TASK-061): успешный вход — кто, когда, откуда, каким способом.
    log_auth_event(
        db,
        "auth_login",
        user,
        request,
        metadata={
            "action": "login_success",
            "auth_source": user.auth_source,
            "auth_method": method,
            "auth_mode": auth_manager.get_current_mode(),
            "roles": [r.name for r in user.roles],
        },
    )

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict(),
    )


@router.get("/mode")
async def get_mode(
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    """Текущий режим аутентификации (для логин-страницы WebUI)."""
    return {"mode": auth_manager.get_current_mode()}


@router.post("/refresh")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    auth_manager: AuthManager = Depends(get_auth_manager),
):
    """Обновление access токена."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required",
        )

    payload = auth_manager.jwt.verify_token(refresh_token, "refresh")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # TASK-013 (BUG-041): ротация refresh — старый jti в blacklist.
    auth_manager.jwt.blacklist_jti(payload)

    user_id = payload.get("user_id")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    token_data = {"user_id": user.id, "username": user.username}
    access_token = auth_manager.jwt.create_access_token(token_data)
    new_refresh = auth_manager.jwt.create_refresh_token(token_data)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=cookie_secure(),  # BUG-042
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=cookie_secure(),  # BUG-042
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Выход из системы. TASK-013 (BUG-041): access/refresh jti → blacklist."""
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
    from .rate_limit import login_limiter as _limiter

    jm = get_auth_manager().jwt
    jti = None
    if token:
        try:
            payload = jm.verify_token(token, "access")
            if payload:
                jti = payload.get("jti")
                jm.blacklist_jti(payload)
        except Exception:  # noqa: BLE001
            pass

    _limiter.reset(f"login:user:{current_user.username}")

    # BUG-095 (TASK-061): выход из системы. Пишем только jti, не сам токен.
    log_auth_event(
        db,
        "auth_logout",
        current_user,
        request,
        metadata={"action": "logout", "jti": jti},
    )

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"status": "ok", "message": "Logged out successfully"}


# ===== ЗАЩИЩЕННЫЕ ЭНДПОИНТЫ =====


@router.get("/me")
async def get_me(current_user: User = Depends(require_auth)):
    """Информация о текущем пользователе."""
    return current_user.to_dict()


@router.post("/change-password")
async def change_password(
    request: Request,
    request_data: ChangePasswordRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Смена пароля (только для локальных пользователей).

    BUG-201 (v3.13.39): пароль не менялся, хотя возвращался 200 OK. Две причины:
      1) AuthMiddleware грузит request.state.user в СВОЕЙ сессии и закрывает её
         после call_next; мутация этого объекта в хендлере не попадала в сессию
         get_db() — фактический commit был пустым;
      2) отдельной проверки хеша в БД не было.
    Решение: пользователь пере-запрашивается в сессии хендлера (db), хеш
    обновляется и коммитится именно там. После commit пишется аудит.
    """
    # user в сессии этого запроса (get_db), а не detached-объект из middleware.
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not user.is_local_user():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change only available for local users",
        )

    if not user.check_password(request_data.old_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    if request_data.confirm_password is not None:
        if request_data.new_password != request_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match",
            )

    if len(request_data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password too short",
        )

    user.set_password(request_data.new_password)
    db.commit()
    # Подтверждаем, что хеш реально обновился в БД (см. BUG-201).
    db.refresh(user)

    # BUG-095 (TASK-062): факт смены пароля. Ни старый, ни новый пароль не пишутся.
    log_auth_event(
        db,
        "user_password_changed",
        user,
        request,
        metadata={
            "action": "password_changed",
            "target_user_id": user.id,
            "target_username": user.username,
            "by_admin": False,
            "self_service": True,
        },
    )

    return {"status": "ok", "message": "Password changed"}


# ===== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (Admin) =====


@router.get("/users", response_model=UserListResponse)
async def list_users(
    search: Optional[str] = None,
    source: Optional[str] = None,
    role: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Список пользователей с фильтрацией и пагинацией (только Admin)."""
    query = db.query(User)

    if search:
        pattern = f"%{search}%"
        query = query.filter((User.username.ilike(pattern)) | (User.full_name.ilike(pattern)))
    if source:
        query = query.filter(User.auth_source == source)
    if role:
        query = query.filter(User.roles.any(Role.name == role))

    total = query.count()
    users = query.order_by(User.id).offset(offset).limit(limit).all()

    return {
        "items": [u.to_dict() for u in users],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/users", response_model=dict)
async def create_user(
    request: Request,
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Создание пользователя (локального или AD-ссылки) (только Admin)."""
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    if user_data.auth_source not in ("local", "ad"):
        raise HTTPException(status_code=400, detail="Invalid auth_source")

    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        auth_source=user_data.auth_source,
        is_active=user_data.is_active,
    )
    # Пароль только для локальных пользователей
    if user_data.auth_source == "local":
        if not user_data.password:
            raise HTTPException(status_code=400, detail="Password required for local user")
        user.set_password(user_data.password)

    for role_name in user_data.roles:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role:
            user.roles.append(role)

    db.add(user)
    db.commit()
    db.refresh(user)

    # BUG-095 (TASK-062): создание пользователя. Пароль не пишется.
    log_auth_event(
        db,
        "user_created",
        admin,
        request,
        metadata={
            "action": "user_created",
            "target_user_id": user.id,
            "target_username": user.username,
            "auth_source": user.auth_source,
            "is_active": user.is_active,
            "roles": [r.name for r in user.roles],
        },
    )

    return user.to_dict()


@router.get("/users/{user_id}", response_model=dict)
async def get_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Информация о пользователе (только Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user.to_dict()


@router.put("/users/{user_id}", response_model=dict)
async def update_user(
    request: Request,
    user_id: int,
    user_data: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Обновление пользователя (только Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles_before = [r.name for r in user.roles]
    changes: dict = {}

    if user_data.email is not None and user_data.email != user.email:
        user.email = user_data.email
        changes["email"] = "changed"  # PII: без значения
    if user_data.full_name is not None and user_data.full_name != user.full_name:
        user.full_name = user_data.full_name
        changes["full_name"] = "changed"  # PII: без значения
    if user_data.auth_source is not None and user_data.auth_source != user.auth_source:
        user.auth_source = user_data.auth_source
        changes["auth_source"] = user_data.auth_source
    if user_data.is_active is not None:
        if user.id == admin.id and user_data.is_active is False:
            raise HTTPException(status_code=400, detail="Cannot disable yourself")
        if user_data.is_active != user.is_active:
            changes["is_active"] = user_data.is_active
        user.is_active = user_data.is_active
    if user_data.password:
        if user.auth_source != "local":
            raise HTTPException(status_code=400, detail="Cannot set password for AD user")
        user.set_password(user_data.password)
        changes["password"] = "changed"  # значение не пишется (и вырезается sanitize)
    if user_data.roles is not None:
        user.roles = []
        for role_name in user_data.roles:
            role = db.query(Role).filter(Role.name == role_name).first()
            if role:
                user.roles.append(role)

    db.commit()
    db.refresh(user)
    roles_after = [r.name for r in user.roles]

    # BUG-095 (TASK-062): изменение пользователя + смена ролей
    if changes or roles_before != roles_after:
        log_auth_event(
            db,
            "user_updated",
            admin,
            request,
            metadata={
                "action": "user_updated",
                "target_user_id": user.id,
                "target_username": user.username,
                "changes": changes,
            },
        )
    if user_data.password:
        # Смена пароля админом — отдельным событием (в user_updated пароль вырезается)
        log_auth_event(
            db,
            "user_password_changed",
            admin,
            request,
            metadata={
                "action": "password_changed",
                "target_user_id": user.id,
                "target_username": user.username,
                "by_admin": admin.id != user.id,
                "self_service": False,
            },
        )
    _log_role_changes(db, admin, request, user, roles_before, roles_after)

    return user.to_dict()


def _log_role_changes(db, admin, request, target, roles_before, roles_after):
    """BUG-095 (TASK-062): role_assigned / role_revoked по разнице ролей."""
    assigned, revoked = role_diff(roles_before, roles_after)
    for role_name in assigned:
        log_auth_event(
            db,
            "role_assigned",
            admin,
            request,
            metadata={
                "action": "role_assigned",
                "target_user_id": target.id,
                "target_username": target.username,
                "role": role_name,
            },
        )
    for role_name in revoked:
        log_auth_event(
            db,
            "role_revoked",
            admin,
            request,
            metadata={
                "action": "role_revoked",
                "target_user_id": target.id,
                "target_username": target.username,
                "role": role_name,
            },
        )


@router.delete("/users/{user_id}")
async def delete_user(
    request: Request,
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Удаление пользователя (только Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    target_username = user.username
    roles_before = [r.name for r in user.roles]

    user.roles = []
    db.delete(user)
    db.commit()

    # BUG-095 (TASK-062): удаление пользователя
    log_auth_event(
        db,
        "user_deleted",
        admin,
        request,
        metadata={
            "action": "user_deleted",
            "target_user_id": user_id,
            "target_username": target_username,
            "roles": roles_before,
        },
    )
    return {"status": "ok", "detail": "User deleted"}


@router.put("/users/{user_id}/status", response_model=dict)
async def update_user_status(
    request: Request,
    user_id: int,
    request_data: UserStatusUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Включение/отключение пользователя (только Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id and not request_data.is_active:
        raise HTTPException(status_code=400, detail="Cannot disable yourself")

    target_username = user.username
    user.is_active = request_data.is_active
    db.commit()

    # BUG-095 (TASK-062): блокировка/разблокировка учётки
    log_auth_event(
        db,
        "user_updated",
        admin,
        request,
        metadata={
            "action": "status_changed",
            "target_user_id": user_id,
            "target_username": target_username,
            "changes": {"is_active": request_data.is_active},
        },
    )
    return {"status": "ok", "user_id": user_id, "is_active": user.is_active}


@router.put("/users/{user_id}/roles", response_model=dict)
async def update_user_roles(
    request: Request,
    user_id: int,
    request_data: UserRoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Обновление ролей пользователя (только Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    roles_before = [r.name for r in user.roles]

    user.roles = []
    for role_name in request_data.roles:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role:
            user.roles.append(role)

    db.commit()
    db.refresh(user)
    roles_after = [r.name for r in user.roles]

    # BUG-095 (TASK-062): role_assigned / role_revoked
    _log_role_changes(db, admin, request, user, roles_before, roles_after)

    return {"status": "ok", "user_id": user_id, "roles": [r.name for r in user.roles]}


# ===== УПРАВЛЕНИЕ РОЛЯМИ (Admin) =====


@router.get("/roles", response_model=RoleListResponse)
async def list_roles(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Список ролей (только Admin)."""
    roles = db.query(Role).order_by(Role.id).all()
    return {"items": [r.to_dict() for r in roles], "total": len(roles)}


@router.post("/roles", response_model=dict)
async def create_role(
    request: Request,
    role_data: RoleCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Создание роли (только Admin).

    BUG-181 (v3.13.39): раньше CRUD ролей не логировался — создать/удалить
    роль можно было без следов в audit_logs.
    """
    existing = db.query(Role).filter(Role.name == role_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Role already exists")

    role = Role(
        name=role_data.name,
        description=role_data.description,
        ad_group=role_data.ad_group,
    )
    meta = {
        "action": "role_created",
        "role_name": role_data.name,
        "ad_group": role_data.ad_group,
    }
    with with_audit(db, "role_created", request=request, user=admin, metadata=meta):
        db.add(role)
        db.flush()
        meta["role_id"] = role.id
    db.refresh(role)
    return role.to_dict()


@router.get("/roles/{role_id}", response_model=dict)
async def get_role(
    role_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Информация о роли (только Admin)."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role.to_dict()


@router.put("/roles/{role_id}", response_model=dict)
async def update_role(
    request: Request,
    role_id: int,
    role_data: RoleUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Обновление роли (только Admin).

    BUG-168 (v3.13.39): системные роли (admin/auditor/scanner/viewer) нельзя
    переименовывать и менять AD-group — иначе RBAC ломается. Допустимо менять
    только description. BUG-181: изменение пишется в audit_logs.
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    changes: dict = {}

    if role.name in SYSTEM_ROLES:
        if role_data.name is not None and role_data.name != role.name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot rename system role",
            )
        if role_data.ad_group is not None and role_data.ad_group != role.ad_group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot change AD group for system role",
            )
        if role_data.description is not None:
            role.description = role_data.description
            changes["description"] = "changed"
    else:
        if role_data.name is not None and role_data.name != role.name:
            role.name = role_data.name
            changes["name"] = "changed"
        if role_data.description is not None and role_data.description != role.description:
            role.description = role_data.description
            changes["description"] = "changed"
        if role_data.ad_group is not None and role_data.ad_group != role.ad_group:
            role.ad_group = role_data.ad_group
            changes["ad_group"] = "changed"

    meta = {
        "action": "role_updated",
        "role_id": role.id,
        "role_name": role.name,
        "changes": changes,
    }
    with with_audit(db, "role_updated", request=request, user=admin, metadata=meta):
        db.flush()
    db.refresh(role)
    return role.to_dict()


@router.delete("/roles/{role_id}")
async def delete_role(
    request: Request,
    role_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Удаление роли (только Admin).

    BUG-168: системные роли не удаляются. BUG-181: удаление пишется в аудит.
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Не удалять системные роли
    if role.name in ("admin", "auditor", "scanner", "viewer"):
        raise HTTPException(status_code=400, detail=f"Cannot delete system role '{role.name}'")

    meta = {
        "action": "role_deleted",
        "role_id": role.id,
        "role_name": role.name,
    }
    with with_audit(db, "role_deleted", request=request, user=admin, metadata=meta):
        role.users = []
        db.delete(role)
        db.flush()
    return {"status": "ok", "detail": "Role deleted"}


@router.get("/check")
async def check_auth(current_user: User = Depends(require_auth)):
    """Проверка авторизации (для WebUI-защиты страниц)."""
    return {"authenticated": True, "user": current_user.to_dict()}
