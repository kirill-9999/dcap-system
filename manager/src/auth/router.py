# manager/src/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from typing import List

from manager.src.db.session import get_db

from .models import User, Role
from .dependencies import get_current_user, require_admin, require_auth
from .schemas import (
    LoginRequest, LoginResponse, UserCreate, UserResponse, ChangePasswordRequest,
)
from .manager import AuthManager
from .rate_limit import login_limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Регистр глобального AuthManager (заполняется в main.py при старте)
_auth_manager: AuthManager = None  # type: ignore


def set_auth_manager(am: AuthManager) -> None:
    global _auth_manager
    _auth_manager = am


def get_auth_manager() -> AuthManager:
    if _auth_manager is None:
        raise HTTPException(500, "AuthManager is not initialized")
    return _auth_manager


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
        secure=False,  # В разработке False, в production — True
        samesite="lax",
        max_age=60 * 60 * 24,  # 24 часа
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,  # 7 дней
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

    payload = auth_manager.jwt.verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

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
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24,
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=False,
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
    response: Response,
    current_user: User = Depends(require_auth),
):
    """Выход из системы."""
    from .rate_limit import login_limiter as _limiter
    _limiter.reset(f"login:user:{current_user.username}")
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
    request_data: ChangePasswordRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Смена пароля (только для локальных пользователей)."""
    if not current_user.is_local_user():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change only available for local users",
        )

    if not current_user.check_password(request_data.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    current_user.set_password(request_data.new_password)
    db.commit()

    return {"status": "ok", "message": "Password changed"}


# ===== АДМИНИСТРАТИВНЫЕ ЭНДПОИНТЫ =====


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Список всех пользователей (только Admin)."""
    users = db.query(User).all()
    return [u.to_dict() for u in users]


@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Создание локального пользователя (только Admin)."""
    existing = db.query(User).filter(
        (User.username == user_data.username) | (
            User.email == user_data.email if user_data.email else False
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists",
        )

    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        auth_source="local",
        is_active=True,
    )
    user.set_password(user_data.password)

    for role_name in user_data.roles:
        role = db.query(Role).filter(Role.name == role_name).first()
        if role:
            user.roles.append(role)

    db.add(user)
    db.commit()
    db.refresh(user)

    return user.to_dict()


@router.put("/users/{user_id}/status")
async def toggle_user_status(
    user_id: int,
    is_active: bool,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Включение/отключение пользователя (только Admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable yourself",
        )

    user.is_active = is_active
    db.commit()

    return {"status": "ok", "user_id": user_id, "is_active": is_active}


@router.get("/check")
async def check_auth(current_user: User = Depends(require_auth)):
    """Проверка авторизации (для WebUI-защиты страниц)."""
    return {"authenticated": True, "user": current_user.to_dict()}
