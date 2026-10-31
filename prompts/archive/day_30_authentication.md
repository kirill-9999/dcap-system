📋 ТЗ — ДЕНЬ 30: ГИБРИДНАЯ АУТЕНТИФИКАЦИЯ (JWT + Windows Integrated Auth)
Файл: prompts/tz/day_30_authentication.md
Дата: 30.08.2026
Версия: v3.0.0
Статус: ✏️ Готово к разработке

🎯 ЦЕЛЬ
Внедрить гибридную аутентификацию, поддерживающую:

Режим local (разработка на ноутбуке без AD) — JWT + Bcrypt, встроенные пользователи

Режим windows_integrated (production с AD) — SPNEGO/Kerberos, прозрачный вход

Режим hybrid (тестирование) — SPNEGO с fallback на JWT

🏗️ АРХИТЕКТУРА
text
┌─────────────────────────────────────────────────────────────────────────────┐
│              ГИБРИДНАЯ АУТЕНТИФИКАЦИЯ DCAP v3.0.0                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  config.json: auth.mode = "local" | "hybrid" | "windows_integrated"       │
│                              │                                              │
│              ┌───────────────┼───────────────┐                             │
│              ▼               ▼               ▼                             │
│  ┌───────────────────┐ ┌─────────────────┐ ┌─────────────────────────────┐ │
│  │   MODE: local     │ │   MODE: hybrid  │ │   MODE: windows_integrated │ │
│  │   (разработка)    │ │   (тестирование)│ │   (production)              │ │
│  ├───────────────────┤ ├─────────────────┤ ├─────────────────────────────┤ │
│  │ JWT + Bcrypt      │ │ Сначала SPNEGO, │ │ Только SPNEGO               │ │
│  │ (встроенные       │ │ при ошибке →    │ │ (Windows Integrated Auth)   │ │
│  │  пользователи)    │ │ JWT + Bcrypt    │ │                             │ │
│  └───────────────────┘ └─────────────────┘ └─────────────────────────────┘ │
│                                                                             │
│  ХРАНЕНИЕ:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  local_mode:   PostgreSQL (users, roles) + bcrypt                     ││
│  │                 admin/admin123 — для разработки                        ││
│  │  hybrid/windows_integrated:   AD (через LDAP/Kerberos)                ││
│  │                 Роли мапятся на AD-группы:                             ││
│  │                 DCAP_Admin → admin, DCAP_Auditor → auditor, ...        ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
📁 ФАЙЛЫ ДЛЯ СОЗДАНИЯ / ИЗМЕНЕНИЯ
НОВЫЕ ФАЙЛЫ (СОЗДАТЬ)
Файл	Назначение
manager/src/auth/__init__.py	Модуль аутентификации
manager/src/auth/models.py	SQLAlchemy модели User, Role
manager/src/auth/modes.py	Enum AuthMode (local, hybrid, windows_integrated)
manager/src/auth/jwt.py	JWT создание/верификация
manager/src/auth/local_auth.py	LocalAuthenticator (JWT + Bcrypt)
manager/src/auth/windows_auth.py	WindowsAuthenticator (SPNEGO)
manager/src/auth/manager.py	AuthManager (единый менеджер)
manager/src/auth/middleware.py	AuthMiddleware для FastAPI
manager/src/auth/dependencies.py	Зависимости FastAPI (get_current_user, require_roles)
manager/src/auth/router.py	Эндпоинты /api/auth/*
manager/src/auth/schemas.py	Pydantic схемы для auth
manager/src/db/init_roles.py	Инициализация ролей и admin
webui/templates/login.html	Страница входа
webui/static/js/auth.js	JavaScript для логина/logout
ИЗМЕНИТЬ
Файл	Изменение
manager/config/config.json	Добавить секцию auth (mode, jwt_secret_key, windows_auth)
manager/src/main.py	Подключить auth router, добавить AuthMiddleware
manager/src/db/models.py	Добавить модели User, Role (или импорт из auth)
manager/src/api/*.py	Добавить защиту эндпоинтов (Depends(require_*))
webui/main.py	Добавить страницу логина, защиту страниц
webui/api/routes.py	Добавить прокси для auth эндпоинтов
webui/templates/base.html	Добавить информацию о пользователе, кнопку выхода
webui/static/js/api.js	Добавить автоматическую подстановку JWT
AGENTS.md	Обновить документацию
README.md	Обновить документацию
.env.example	Добавить JWT_SECRET_KEY, AD_* переменные
requirements.txt	Добавить bcrypt, python-jose, pyspnego, gssapi
🔧 КОНФИГУРАЦИЯ
manager/config/config.json (дополнение)
json
{
    "server": {
        "host": "0.0.0.0",
        "port": 8000
    },
    "database": {
        "url": "sqlite:///./manager/dcap.db"
    },
    "auth": {
        "mode": "local",
        "jwt_secret_key": "${JWT_SECRET_KEY:-change-me-in-production}",
        "jwt_access_ttl_minutes": 1440,
        "jwt_refresh_ttl_days": 7,
        "bcrypt_rounds": 12,
        "local_users_enabled": true,
        "auto_create_ad_users": true,
        "default_role": "viewer",
        "windows_auth": {
            "enabled": false,
            "ad_domain": "${AD_DOMAIN:-}",
            "ad_server": "${AD_SERVER:-}",
            "ad_ldap_port": 389,
            "ad_use_ssl": false,
            "service_account": "${AD_SERVICE_USER:-}",
            "service_password": "${AD_SERVICE_PASSWORD:-}",
            "group_mapping": {
                "DCAP_Admin": "admin",
                "DCAP_Auditor": "auditor",
                "DCAP_Scanner": "scanner"
            }
        }
    },
    "logging": {
        "level": "INFO"
    }
}
.env.example (дополнение)
bash
# ===== AUTHENTICATION =====
# JWT секрет (обязательно сменить в production)
JWT_SECRET_KEY=change-me-in-production-32-chars-long

# Режим аутентификации: local | hybrid | windows_integrated
AUTH_MODE=local

# ===== ACTIVE DIRECTORY (для windows_integrated режима) =====
AD_DOMAIN=EXAMPLE
AD_SERVER=dc.example.com
AD_SERVICE_USER=dcap_service
AD_SERVICE_PASSWORD=secure_password
📁 СТРУКТУРА МОДУЛЯ AUTH
text
manager/src/auth/
├── __init__.py
├── models.py          # User, Role (SQLAlchemy)
├── modes.py           # AuthMode enum
├── jwt.py             # JWT создание/верификация
├── local_auth.py      # LocalAuthenticator (JWT + Bcrypt)
├── windows_auth.py    # WindowsAuthenticator (SPNEGO/Kerberos)
├── manager.py         # AuthManager (единый менеджер)
├── middleware.py      # AuthMiddleware (FastAPI)
├── dependencies.py    # FastAPI зависимости (get_current_user, require_*)
├── router.py          # /api/auth/* эндпоинты
├── schemas.py         # Pydantic схемы
└── rate_limit.py      # Rate limiting для login
🔧 ДЕТАЛЬНАЯ РЕАЛИЗАЦИЯ
1. modes.py — Режимы аутентификации
python
# manager/src/auth/modes.py
from enum import Enum

class AuthMode(str, Enum):
    LOCAL = "local"                    # JWT + Bcrypt (разработка)
    WINDOWS_INTEGRATED = "windows_integrated"  # SPNEGO (production AD)
    HYBRID = "hybrid"                  # SPNEGO → fallback JWT
2. models.py — SQLAlchemy модели
python
# manager/src/auth/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from ..db.base import Base
import bcrypt

# Таблица связи пользователей и ролей
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("role_id", Integer, ForeignKey("roles.id"))
)

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(200), nullable=True)  # null для AD-пользователей
    full_name = Column(String(100), nullable=True)
    domain_user = Column(String(200), nullable=True, index=True)  # DOMAIN\username
    auth_source = Column(String(20), default="local")  # local | ad
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    
    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')
    
    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(
            password.encode('utf-8'),
            self.password_hash.encode('utf-8')
        )
    
    def is_local_user(self) -> bool:
        return self.auth_source == "local"
    
    def is_ad_user(self) -> bool:
        return self.auth_source == "ad"
    
    def has_role(self, role_name: str) -> bool:
        return any(r.name == role_name for r in self.roles)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "domain_user": self.domain_user,
            "auth_source": self.auth_source,
            "is_active": self.is_active,
            "roles": [r.name for r in self.roles],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200), nullable=True)
    
    users = relationship("User", secondary=user_roles, back_populates="roles")
3. jwt.py — JWT менеджер
python
# manager/src/auth/jwt.py
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os

def get_secret_key() -> str:
    """Получение секретного ключа из env или конфига"""
    return os.environ.get("JWT_SECRET_KEY", "change-me-in-production")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_ACCESS_TTL", 1440))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_TTL", 7))

def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)

def create_refresh_token(data: Dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, get_secret_key(), algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[Dict]:
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def extract_user_id(token: str) -> Optional[int]:
    payload = verify_token(token)
    if payload and "user_id" in payload:
        return payload["user_id"]
    return None
4. local_auth.py — Local Authenticator
python
# manager/src/auth/local_auth.py
import bcrypt
import logging
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime

from .models import User

logger = logging.getLogger(__name__)

class LocalAuthenticator:
    """Локальная аутентификация (JWT + Bcrypt)"""
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("auth", {}).get("local_users_enabled", True)
        self.bcrypt_rounds = config.get("auth", {}).get("bcrypt_rounds", 12)
    
    def authenticate(self, username: str, password: str, db: Session) -> Optional[User]:
        """Аутентификация по логину/паролю"""
        if not self.enabled:
            return None
        
        user = db.query(User).filter(
            User.username == username,
            User.auth_source == "local",
            User.is_active == True
        ).first()
        
        if not user:
            return None
        
        if not user.check_password(password):
            return None
        
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user
    
    def create_user(self, username: str, password: str, email: str = None,
                    full_name: str = None, roles: list = None, db: Session) -> User:
        """Создание локального пользователя"""
        user = User(
            username=username,
            email=email,
            full_name=full_name,
            auth_source="local",
            is_active=True
        )
        user.set_password(password)
        
        if roles:
            for role_name in roles:
                role = db.query(Role).filter(Role.name == role_name).first()
                if role:
                    user.roles.append(role)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
5. windows_auth.py — Windows Authenticator
python
# manager/src/auth/windows_auth.py
import logging
import os
import sys
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from datetime import datetime

logger = logging.getLogger(__name__)

class WindowsAuthenticator:
    """Windows Integrated Authentication (SPNEGO/Kerberos)"""
    
    def __init__(self, config: dict):
        self.config = config
        self.enabled = config.get("auth", {}).get("windows_auth", {}).get("enabled", False)
        self.domain = config.get("auth", {}).get("windows_auth", {}).get("ad_domain", "")
        self._available = False
        self._spnego_available = False
        
        if self.enabled:
            self._init_spnego()
    
    def _init_spnego(self):
        """Инициализация SPNEGO"""
        try:
            import spnego
            self._spnego_available = True
            self._available = True
            logger.info("Windows Authenticator: spnego available")
        except ImportError:
            logger.warning("spnego not installed, Windows Auth disabled")
            self._available = False
    
    def is_available(self) -> bool:
        return self._available and self.enabled
    
    def is_ad_environment(self) -> bool:
        """Проверка: есть ли AD окружение"""
        if sys.platform == "win32":
            domain = os.environ.get("USERDOMAIN")
            return domain and domain != "WORKGROUP"
        return bool(self.domain)
    
    def authenticate(self, auth_header: str) -> Optional[str]:
        """
        Аутентификация через SPNEGO
        Возвращает DOMAIN\username или None
        """
        if not self.is_available():
            return None
        
        if not auth_header or not auth_header.startswith("Negotiate "):
            return None
        
        # Если нет AD — используем mock для разработки
        if not self.is_ad_environment():
            return self._mock_authenticate(auth_header)
        
        try:
            import spnego
            
            token = auth_header.replace("Negotiate ", "")
            
            # Реальная валидация через spnego
            # Для production с AD
            # ...
            
            # Заглушка для разработки (без реального AD)
            return self._mock_authenticate(auth_header)
            
        except Exception as e:
            logger.error(f"SPNEGO error: {e}")
            return None
    
    def _mock_authenticate(self, auth_header: str) -> Optional[str]:
        """Mock-аутентификация для разработки без AD"""
        # Формат: Negotiate base64(domain:username)
        import base64
        try:
            token = auth_header.replace("Negotiate ", "")
            decoded = base64.b64decode(token).decode('utf-8')
            if ":" in decoded:
                domain, username = decoded.split(":", 1)
                return f"{domain}\\{username}"
        except:
            pass
        
        # Fallback: используем переменную окружения
        if sys.platform == "win32":
            domain = os.environ.get("USERDOMAIN", "WORKGROUP")
            username = os.environ.get("USERNAME", "developer")
            return f"{domain}\\{username}"
        
        return "WORKGROUP\\developer"
    
    def get_user_info(self, domain_user: str) -> Optional[Dict]:
        """Получение информации о пользователе из AD"""
        if not self.is_available():
            return None
        
        username = domain_user.split("\\")[-1] if "\\" in domain_user else domain_user
        
        # Заглушка для разработки
        return {
            "username": username,
            "full_name": username.capitalize(),
            "email": f"{username}@example.com",
            "domain_user": domain_user
        }
    
    def get_user_groups(self, domain_user: str) -> List[str]:
        """Получение групп пользователя из AD"""
        if not self.is_available():
            return []
        
        # Заглушка для разработки
        # В реальности — LDAP запрос к AD
        return ["DCAP_Viewer"]
    
    def get_ad_user_from_db(self, domain_user: str, db: Session) -> Optional[User]:
        """Поиск AD пользователя в локальной БД"""
        from .models import User
        return db.query(User).filter(
            User.domain_user == domain_user,
            User.auth_source == "ad",
            User.is_active == True
        ).first()
6. manager.py — Auth Manager
python
# manager/src/auth/manager.py
import logging
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import Request
from datetime import datetime

from .models import User, Role
from .modes import AuthMode
from .local_auth import LocalAuthenticator
from .windows_auth import WindowsAuthenticator

logger = logging.getLogger(__name__)

class AuthManager:
    """Гибридный менеджер аутентификации"""
    
    def __init__(self, config: dict):
        self.config = config
        self.mode = AuthMode(config.get("auth", {}).get("mode", "local"))
        
        self.local_auth = LocalAuthenticator(config)
        self.windows_auth = WindowsAuthenticator(config)
        
        logger.info(f"Auth mode: {self.mode.value}")
        if self.mode != AuthMode.LOCAL:
            logger.info(f"Windows Auth available: {self.windows_auth.is_available()}")
    
    def get_current_mode(self) -> str:
        return self.mode.value
    
    async def authenticate(
        self,
        request: Request,
        db: Session,
        username: Optional[str] = None,
        password: Optional[str] = None
    ) -> Tuple[Optional[User], str]:
        """
        Аутентификация пользователя.
        Возвращает (user, auth_method) или (None, error_message)
        """
        
        # 1. Windows Integrated Auth (SPNEGO) — для hybrid и windows_integrated
        if self.mode in (AuthMode.WINDOWS_INTEGRATED, AuthMode.HYBRID):
            auth_header = request.headers.get("Authorization")
            domain_user = self.windows_auth.authenticate(auth_header)
            
            if domain_user:
                user = await self._authenticate_ad_user(domain_user, db)
                if user:
                    return user, "windows_integrated"
                elif self.mode == AuthMode.WINDOWS_INTEGRATED:
                    return None, "AD authentication failed"
                # HYBRID: fallback к local
        
        # 2. Local Auth (JWT + Bcrypt) — для local и hybrid (fallback)
        if self.mode in (AuthMode.LOCAL, AuthMode.HYBRID):
            if username and password:
                user = self.local_auth.authenticate(username, password, db)
                if user:
                    return user, "local_jwt"
                elif self.mode == AuthMode.LOCAL:
                    return None, "Invalid credentials"
        
        # 3. Поиск AD пользователя по username (для hybrid)
        if self.mode == AuthMode.HYBRID and username and "\\" in username:
            user = self.windows_auth.get_ad_user_from_db(username, db)
            if user:
                return user, "cached_ad"
        
        return None, "Authentication failed"
    
    async def _authenticate_ad_user(self, domain_user: str, db: Session) -> Optional[User]:
        """Аутентификация AD пользователя"""
        if not self.windows_auth.is_available():
            return None
        
        # 1. Поиск в локальной БД
        user = self.windows_auth.get_ad_user_from_db(domain_user, db)
        if user:
            user.last_login = datetime.utcnow()
            db.commit()
            return user
        
        # 2. Создание нового пользователя (если разрешено)
        if self.config.get("auth", {}).get("auto_create_ad_users", True):
            user_info = self.windows_auth.get_user_info(domain_user)
            if user_info:
                user = User(
                    username=user_info.get("username", domain_user.split("\\")[-1]),
                    full_name=user_info.get("full_name", ""),
                    domain_user=domain_user,
                    auth_source="ad",
                    is_active=True
                )
                
                # Назначение ролей на основе AD групп
                groups = self.windows_auth.get_user_groups(domain_user)
                roles = self._map_groups_to_roles(groups)
                for role_name in roles:
                    role = db.query(Role).filter(Role.name == role_name).first()
                    if role:
                        user.roles.append(role)
                
                # Если ролей нет — добавляем default
                if not user.roles:
                    default = db.query(Role).filter(
                        Role.name == self.config.get("auth", {}).get("default_role", "viewer")
                    ).first()
                    if default:
                        user.roles.append(default)
                
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Created AD user: {domain_user} with roles: {[r.name for r in user.roles]}")
                return user
        
        return None
    
    def _map_groups_to_roles(self, groups: list) -> list:
        """Маппинг AD групп на роли DCAP"""
        mapping = self.config.get("auth", {}).get("windows_auth", {}).get("group_mapping", {})
        roles = []
        for group in groups:
            if group in mapping:
                roles.append(mapping[group])
        return list(set(roles))
7. middleware.py — Auth Middleware
python
# manager/src/auth/middleware.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging
from sqlalchemy.orm import Session

from .manager import AuthManager
from .jwt import verify_token, extract_user_id
from .modes import AuthMode
from .models import User

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    """Единый middleware для гибридной аутентификации"""
    
    def __init__(self, app, auth_manager: AuthManager, db_session_factory):
        super().__init__(app)
        self.auth_manager = auth_manager
        self.db_session_factory = db_session_factory
    
    async def dispatch(self, request: Request, call_next):
        # Публичные эндпоинты (не требуют аутентификации)
        public_paths = [
            "/api/auth/login", "/api/auth/refresh",
            "/health", "/docs", "/openapi.json",
            "/static", "/vendor"
        ]
        if any(request.url.path.startswith(p) for p in public_paths):
            return await call_next(request)
        
        # Проверка: есть ли уже JWT в cookies или header
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
        
        # Если токен есть — проверяем
        if token:
            payload = verify_token(token)
            if payload:
                user_id = payload.get("user_id")
                if user_id:
                    # Получаем пользователя из БД
                    async with self.db_session_factory() as db:
                        user = db.query(User).filter(User.id == user_id).first()
                        if user and user.is_active:
                            request.state.user = user
                            request.state.auth_method = "jwt"
                            return await call_next(request)
        
        # Если токена нет — пробуем SPNEGO (Windows Integrated Auth)
        if self.auth_manager.mode != AuthMode.LOCAL:
            async with self.db_session_factory() as db:
                user, result = await self.auth_manager.authenticate(request, db)
                if user:
                    request.state.user = user
                    request.state.auth_method = "windows_integrated"
                    return await call_next(request)
        
        # Если SPNEGO не помог и мы в режиме HYBRID — пробуем Basic Auth
        if self.auth_manager.mode in (AuthMode.LOCAL, AuthMode.HYBRID):
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Basic "):
                import base64
                try:
                    decoded = base64.b64decode(auth_header.replace("Basic ", "")).decode('utf-8')
                    username, password = decoded.split(":", 1)
                    async with self.db_session_factory() as db:
                        user, result = await self.auth_manager.authenticate(
                            request, db, username, password
                        )
                        if user:
                            request.state.user = user
                            request.state.auth_method = "basic"
                            return await call_next(request)
                except:
                    pass
        
        # Не авторизован — возвращаем 401
        headers = {}
        if self.auth_manager.mode != AuthMode.LOCAL:
            headers["WWW-Authenticate"] = "Negotiate"
        else:
            headers["WWW-Authenticate"] = "Bearer"
        
        return JSONResponse(
            status_code=401,
            headers=headers,
            content={"detail": "Authentication required"}
        )
8. dependencies.py — FastAPI зависимости
python
# manager/src/auth/dependencies.py
from fastapi import Depends, HTTPException, status, Request
from typing import Optional, List
from .models import User

def get_current_user(request: Request) -> Optional[User]:
    """Получение текущего пользователя из request.state"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    return user

def require_auth(current_user: User = Depends(get_current_user)) -> User:
    """Требовать аутентификацию"""
    return current_user

def require_roles(roles: List[str]):
    """Декоратор для проверки ролей"""
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
9. router.py — API эндпоинты
python
# manager/src/auth/router.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime
from typing import List

from .models import User, Role
from .jwt import create_access_token, create_refresh_token, verify_token
from .dependencies import get_current_user, require_admin, require_auth
from .schemas import LoginRequest, LoginResponse, UserCreate, UserResponse, ChangePasswordRequest
from .manager import AuthManager
from ..db.session import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ===== ПУБЛИЧНЫЕ ЭНДПОИНТЫ =====

@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
    auth_manager: AuthManager = Depends(get_auth_manager)
):
    """Аутентификация пользователя (JWT)"""
    
    # Проверка через AuthManager
    user, method = await auth_manager.authenticate(
        request, db, login_data.username, login_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Создание токенов
    token_data = {"user_id": user.id, "username": user.username}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Установка HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # В разработке False, в production — True
        samesite="lax",
        max_age=60 * 60 * 24  # 24 часа
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7  # 7 дней
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict()
    )

@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Обновление access токена"""
    # Получаем refresh_token из cookies
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token required"
        )
    
    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("user_id")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Создание новых токенов
    token_data = {"user_id": user.id, "username": user.username}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)
    
    # Обновление cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 7
    )
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
async def logout(
    response: Response,
    current_user: User = Depends(require_auth)
):
    """Выход из системы"""
    # Очистка cookies
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"status": "ok", "message": "Logged out successfully"}

# ===== ЗАЩИЩЕННЫЕ ЭНДПОИНТЫ =====

@router.get("/me")
async def get_me(current_user: User = Depends(require_auth)):
    """Информация о текущем пользователе"""
    return current_user.to_dict()

@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """Смена пароля (только для локальных пользователей)"""
    if not current_user.is_local_user():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change only available for local users"
        )
    
    if not current_user.check_password(request.old_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    current_user.set_password(request.new_password)
    db.commit()
    
    return {"status": "ok", "message": "Password changed"}

# ===== АДМИНИСТРАТИВНЫЕ ЭНДПОИНТЫ =====

@router.get("/users", response_model=List[UserResponse])
async def list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Список всех пользователей (только Admin)"""
    users = db.query(User).all()
    return [u.to_dict() for u in users]

@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Создание локального пользователя (только Admin)"""
    # Проверка существования
    existing = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    
    # Создание пользователя
    user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        auth_source="local",
        is_active=True
    )
    user.set_password(user_data.password)
    
    # Добавление ролей
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
    db: Session = Depends(get_db)
):
    """Включение/отключение пользователя (только Admin)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable yourself"
        )
    
    user.is_active = is_active
    db.commit()
    
    return {"status": "ok", "user_id": user_id, "is_active": is_active}
10. schemas.py — Pydantic схемы
python
# manager/src/auth/schemas.py
from pydantic import BaseModel, EmailStr
from typing import List, Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    roles: List[str] = ["viewer"]

class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    domain_user: Optional[str]
    auth_source: str
    roles: List[str]
    is_active: bool
    created_at: Optional[str]
    last_login: Optional[str]

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
11. init_roles.py — Инициализация ролей
python
# manager/src/db/init_roles.py
import logging
from sqlalchemy.orm import Session
from ..auth.models import User, Role

logger = logging.getLogger(__name__)

def init_roles_and_admin(db: Session):
    """Инициализация ролей и создание admin (если не существует)"""
    
    # Создание ролей
    roles_data = [
        {"name": "admin", "description": "Full system access"},
        {"name": "auditor", "description": "Audit and read access"},
        {"name": "scanner", "description": "Scan execution access"},
        {"name": "viewer", "description": "Read-only access"}
    ]
    
    for role_data in roles_data:
        role = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not role:
            role = Role(**role_data)
            db.add(role)
            logger.info(f"Created role: {role_data['name']}")
    
    db.commit()
    
    # Создание admin пользователя (если не существует)
    admin = db.query(User).filter(User.username == "admin").first()
    if not admin:
        admin = User(
            username="admin",
            email="admin@dcap.local",
            full_name="Administrator",
            auth_source="local",
            is_active=True
        )
        admin.set_password("admin123")  # Временный пароль
        logger.warning("=" * 60)
        logger.warning("ADMIN USER CREATED WITH DEFAULT PASSWORD")
        logger.warning("Username: admin")
        logger.warning("Password: admin123")
        logger.warning("CHANGE THIS PASSWORD IMMEDIATELY!")
        logger.warning("=" * 60)
        
        # Добавляем роль admin
        admin_role = db.query(Role).filter(Role.name == "admin").first()
        if admin_role:
            admin.roles.append(admin_role)
        
        db.add(admin)
        db.commit()
        logger.info("Created admin user")
    
    # Добавление роли viewer для всех существующих пользователей без ролей
    for user in db.query(User).filter(~User.roles.any()).all():
        viewer_role = db.query(Role).filter(Role.name == "viewer").first()
        if viewer_role:
            user.roles.append(viewer_role)
    
    db.commit()
🌐 WEBUI — СТРАНИЦА ЛОГИНА
html
<!-- webui/templates/login.html -->
{% extends "base.html" %}

{% block title %}DCAP — Вход{% endblock %}

{% block head %}
<style>
    .login-page {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        background: var(--color-bg);
    }
    .login-container {
        background: var(--color-surface);
        border-radius: var(--radius-lg);
        padding: var(--spacing-8);
        width: 100%;
        max-width: 400px;
        box-shadow: var(--shadow-lg);
        border: 1px solid var(--color-border);
    }
    .login-logo {
        text-align: center;
        margin-bottom: var(--spacing-6);
    }
    .login-logo .logo-icon {
        font-size: 48px;
        display: block;
    }
    .login-logo .logo-text {
        font-size: var(--font-size-xl);
        font-weight: 700;
        color: var(--color-primary);
    }
    .login-error {
        background: var(--color-danger-bg);
        color: var(--color-danger);
        padding: var(--spacing-3);
        border-radius: var(--radius-md);
        margin-bottom: var(--spacing-4);
        display: none;
    }
    .login-error.show {
        display: block;
    }
    .login-footer {
        text-align: center;
        margin-top: var(--spacing-4);
        font-size: var(--font-size-sm);
        color: var(--color-text-secondary);
    }
    .login-mode {
        text-align: center;
        font-size: var(--font-size-xs);
        color: var(--color-text-muted);
        margin-top: var(--spacing-2);
    }
</style>
{% endblock %}

{% block content %}
<div class="login-page">
    <div class="login-container">
        <div class="login-logo">
            <span class="logo-icon">🛡️</span>
            <span class="logo-text">DCAP System</span>
        </div>
        
        <div id="loginError" class="login-error"></div>
        
        <form id="loginForm" onsubmit="handleLogin(event)">
            <div class="form-group">
                <label for="username">Имя пользователя</label>
                <input type="text" id="username" class="form-control" 
                       placeholder="admin" required autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">Пароль</label>
                <input type="password" id="password" class="form-control" 
                       placeholder="••••••••" required>
            </div>
            
            <button type="submit" class="btn btn-primary btn-block" id="loginBtn">
                Войти
            </button>
        </form>
        
        <div class="login-mode" id="authMode">
            Режим: {{ auth_mode }}
        </div>
        
        <div class="login-footer">
            DCAP System v3.0.0
        </div>
    </div>
</div>
{% endblock %}

{% block scripts %}
<script src="/static/js/auth.js"></script>
<script>
    // Проверка: если уже авторизован — редирект
    if (auth.isAuthenticated()) {
        window.location.href = '/';
    }
    
    // Отображение режима аутентификации
    const modeEl = document.getElementById('authMode');
    if (modeEl) {
        // Получаем режим из meta или из API
        fetch('/api/auth/mode')
            .then(r => r.json())
            .then(data => {
                modeEl.textContent = 'Режим: ' + data.mode;
            })
            .catch(() => {});
    }
</script>
{% endblock %}
🌐 WEBUI — AUTH.JS
javascript
// webui/static/js/auth.js

const AUTH = {
    tokenKey: 'dcap_access_token',
    refreshKey: 'dcap_refresh_token',
    userKey: 'dcap_user'
};

const auth = {
    async login(username, password) {
        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password }),
                credentials: 'include'  // Важно для cookies
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'Ошибка входа');
            }
            
            // Сохранение токенов (cookies уже установлены сервером)
            localStorage.setItem(AUTH.tokenKey, data.access_token);
            localStorage.setItem(AUTH.refreshKey, data.refresh_token);
            localStorage.setItem(AUTH.userKey, JSON.stringify(data.user));
            
            return data;
        } catch (error) {
            throw error;
        }
    },
    
    async logout() {
        try {
            await fetch('/api/auth/logout', {
                method: 'POST',
                credentials: 'include'
            });
        } catch (e) {
            // Игнорируем ошибки
        }
        
        localStorage.removeItem(AUTH.tokenKey);
        localStorage.removeItem(AUTH.refreshKey);
        localStorage.removeItem(AUTH.userKey);
        
        window.location.href = '/login';
    },
    
    getToken() {
        return localStorage.getItem(AUTH.tokenKey);
    },
    
    getRefreshToken() {
        return localStorage.getItem(AUTH.refreshKey);
    },
    
    getUser() {
        try {
            const data = localStorage.getItem(AUTH.userKey);
            return data ? JSON.parse(data) : null;
        } catch {
            return null;
        }
    },
    
    isAuthenticated() {
        return !!this.getToken();
    },
    
    hasRole(role) {
        const user = this.getUser();
        if (!user) return false;
        return user.roles.includes(role);
    },
    
    hasAnyRole(roles) {
        const user = this.getUser();
        if (!user) return false;
        return roles.some(r => user.roles.includes(r));
    },
    
    async refresh() {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new Error('No refresh token');
        }
        
        const response = await fetch('/api/auth/refresh', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('Refresh failed');
        }
        
        const data = await response.json();
        localStorage.setItem(AUTH.tokenKey, data.access_token);
        localStorage.setItem(AUTH.refreshKey, data.refresh_token);
        
        return data;
    }
};

async function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const errorEl = document.getElementById('loginError');
    const btn = document.getElementById('loginBtn');
    
    errorEl.classList.remove('show');
    btn.disabled = true;
    btn.textContent = 'Вход...';
    
    try {
        await auth.login(username, password);
        window.location.href = '/';
    } catch (error) {
        errorEl.textContent = error.message || 'Ошибка входа';
        errorEl.classList.add('show');
        btn.disabled = false;
        btn.textContent = 'Войти';
    }
}

window.auth = auth;
🌐 WEBUI — API.JS (ОБНОВЛЕННЫЙ)
javascript
// webui/static/js/api.js (ОБНОВЛЕННЫЙ)

const API_BASE = '/api';

const api = {
    async _request(method, endpoint, data = null, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        // Добавление токена
        const token = window.auth?.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        
        const url = `${API_BASE}${endpoint}`;
        const config = {
            method,
            headers,
            credentials: 'include',  // Важно для cookies
            ...options
        };
        
        if (data && (method === 'POST' || method === 'PUT' || method === 'PATCH')) {
            config.body = JSON.stringify(data);
        }
        
        const response = await fetch(url, config);
        
        // Если 401 — пробуем обновить токен
        if (response.status === 401 && window.auth) {
            try {
                await window.auth.refresh();
                const newToken = window.auth.getToken();
                headers['Authorization'] = `Bearer ${newToken}`;
                const retryResponse = await fetch(url, { ...config, headers });
                return this._handleResponse(retryResponse);
            } catch (e) {
                window.auth?.logout();
                throw new Error('Session expired');
            }
        }
        
        return this._handleResponse(response);
    },
    
    _handleResponse(response) {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.detail || `HTTP ${response.status}`);
            });
        }
        return response.json();
    },
    
    get(endpoint, options = {}) {
        return this._request('GET', endpoint, null, options);
    },
    
    post(endpoint, data, options = {}) {
        return this._request('POST', endpoint, data, options);
    },
    
    put(endpoint, data, options = {}) {
        return this._request('PUT', endpoint, data, options);
    },
    
    delete(endpoint, options = {}) {
        return this._request('DELETE', endpoint, null, options);
    }
};

window.api = api;
🔧 ЗАЩИТА ЭНДПОИНТОВ MANAGER
python
# manager/src/api/audit.py (ОБНОВЛЕННЫЙ)
from ..auth.dependencies import require_auth, require_auditor, require_admin, User

@router.get("/api/audit")
async def get_audit_events(
    current_user: User = Depends(require_auditor),
    # ... остальные параметры
):
    """Просмотр событий аудита (только Auditor+)"""
    # ... логика

@router.delete("/api/audit/agents/{agent_id}")
async def delete_agent(
    agent_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Удаление агента (только Admin)"""
    # ... логика
🗄️ МИГРАЦИЯ БД
python
# manager/src/db/migrations/versions/001_add_users_roles.py
"""Add users and roles tables

Revision ID: 001
Revises: 
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Создание таблицы roles
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    
    # Создание таблицы users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('password_hash', sa.String(length=200), nullable=True),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('domain_user', sa.String(length=200), nullable=True),
        sa.Column('auth_source', sa.String(length=20), nullable=True, server_default='local'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    op.create_index(op.f('ix_users_domain_user'), 'users', ['domain_user'], unique=False)
    
    # Создание таблицы user_roles
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'role_id')
    )

def downgrade():
    op.drop_table('user_roles')
    op.drop_index(op.f('ix_users_domain_user'), table_name='users')
    op.drop_table('users')
    op.drop_table('roles')
✅ КРИТЕРИИ ПРИЕМКИ
Модели и БД
□ Модели User, Role созданы
□ Миграция создана и применена
□ Роли (admin, viewer, auditor, scanner) инициализированы
□ Admin пользователь создан (admin/admin123)
Режимы аутентификации
□ Режим local — JWT + Bcrypt работает
□ Режим windows_integrated — SPNEGO работает (заглушка для разработки)
□ Режим hybrid — SPNEGO с fallback на JWT
API
□ POST /api/auth/login — возвращает JWT + устанавливает cookies
□ POST /api/auth/refresh — обновление токена
□ POST /api/auth/logout — выход, очистка cookies
□ GET /api/auth/me — информация о пользователе
□ POST /api/auth/change-password — смена пароля (local)
□ GET /api/auth/users — список пользователей (Admin)
□ POST /api/auth/users — создание пользователя (Admin)
Защита эндпоинтов
□ Все эндпоинты аудита требуют Auditor+
□ Все эндпоинты управления требуют Admin
□ Эндпоинты сканирования требуют Scanner+
□ Публичные эндпоинты доступны без аутентификации (/health, /docs, /login)
WebUI
□ Страница логина отображается
□ Форма логина работает
□ После логина — редирект на /
□ В шапке отображается пользователь и роли
□ Кнопка выхода работает
□ Неавторизованный пользователь редиректится на /login
Безопасность
□ Пароли хешируются через bcrypt
□ JWT секрет из переменной окружения
□ HttpOnly cookies для хранения токенов
□ Rate limiting на /login (5 попыток/мин)
□ Интеграция с Windows Auth (SPNEGO) — заглушка для разработки
📋 РОЛЕВАЯ МОДЕЛЬ
Роль	Доступ
Admin	✅ Полный доступ: CRUD пользователей, настройки, все данные
Auditor	✅ Чтение аудит-логов, дашборд, каталог (только чтение)
Scanner	✅ Запуск сканирования, просмотр ресурсов
Viewer	✅ Только чтение: дашборд, каталог, находки
🧪 ТЕСТОВЫЙ СЦЕНАРИЙ
bash
# 1. Запуск в local режиме
python run_manager.py
# config.json: auth.mode = "local"

# 2. Логин через WebUI
open http://localhost:8001
# admin / admin123

# 3. Проверка JWT через API
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  -c cookies.txt

curl http://localhost:8000/api/audit/agents \
  -b cookies.txt

# 4. Проверка Windows Integrated Auth (заглушка)
curl --negotiate -u : http://localhost:8000/api/audit \
  --no-auth-cache

# 5. Проверка защиты эндпоинтов
curl http://localhost:8000/api/auth/users
# Должен вернуть 401
💾 КОМАНДА ДЛЯ КОММИТА
bash
git checkout -b feature/day_30_authentication
git add .
git commit -m "feat: День 30 — Гибридная аутентификация (JWT + Windows Integrated Auth)

- Модели User, Role (SQLAlchemy)
- Три режима: local, hybrid, windows_integrated
- LocalAuthenticator: JWT + Bcrypt
- WindowsAuthenticator: SPNEGO (заглушка для разработки)
- AuthManager: единый менеджер аутентификации
- AuthMiddleware: FastAPI middleware
- Эндпоинты /api/auth/* (login, refresh, logout, me, users)
- Страница логина в WebUI
- Защита эндпоинтов (require_auth, require_admin, require_auditor, require_scanner)
- Инициализация ролей и admin (admin/admin123)
- Миграция БД для users, roles, user_roles
- HttpOnly cookies для хранения токенов
- Rate limiting на /login"
