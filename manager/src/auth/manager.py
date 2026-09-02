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
from .ad_auth import ADAuthenticator
from .jwt import JWTManager

logger = logging.getLogger(__name__)


class AuthManager:
    """Гибридный менеджер аутентификации."""

    def __init__(self, config: dict):
        self.config = config
        self.mode = AuthMode(config.get("auth", {}).get("mode", "local"))

        self.local_auth = LocalAuthenticator(config)
        self.windows_auth = WindowsAuthenticator(config)
        self.ad_auth = ADAuthenticator(config)

        auth_cfg = config.get("auth", {})
        self.jwt = JWTManager(
            secret_key=auth_cfg.get("jwt_secret_key"),
            access_ttl_minutes=int(auth_cfg.get("jwt_access_ttl_minutes", 1440)),
            refresh_ttl_days=int(auth_cfg.get("jwt_refresh_ttl_days", 7)),
        )

        logger.info(f"Auth mode: {self.mode.value}")
        if self.mode != AuthMode.LOCAL:
            logger.info(f"Windows Auth available: {self.windows_auth.is_available()}")

    def get_current_mode(self) -> str:
        return self.mode.value

    def is_protected_mode(self) -> bool:
        """Истина, когда запрос к /api/* нужно аутентифицировать."""
        return True

    async def authenticate_windows(self, request: Request, db: Session) -> Optional[User]:
        """Только SPNEGO (для hybrid/windows_integrated). Возвращает User или None."""
        if self.mode not in (AuthMode.WINDOWS_INTEGRATED, AuthMode.HYBRID):
            return None
        auth_header = request.headers.get("Authorization")
        domain_user = self.windows_auth.authenticate(auth_header)
        if not domain_user:
            return None
        return await self._authenticate_ad_user(domain_user, db)

    async def authenticate(
        self,
        request: Request,
        db: Session,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Tuple[Optional[User], str]:
        """
        Аутентификация пользователя.
        Возвращает (user, auth_method) или (None, error_message).
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

        # 2. Explicit AD login (пароль) — доступен в hybrid/windows_integrated/ad
        if self.mode != AuthMode.LOCAL and username and password:
            user = await self._authenticate_ad_password(db, username, password)
            if user:
                return user, "ad_password"

        # 3. Local Auth (JWT + Bcrypt) — для local и hybrid (fallback)
        if self.mode in (AuthMode.LOCAL, AuthMode.HYBRID):
            if username and password:
                user = self.local_auth.authenticate(username, password, db)
                if user:
                    return user, "local_jwt"
                elif self.mode == AuthMode.LOCAL:
                    return None, "Invalid credentials"

        # 4. Поиск AD пользователя по username (для hybrid)
        if self.mode == AuthMode.HYBRID and username and "\\" in username:
            user = self.windows_auth.get_ad_user_from_db(username, db)
            if user:
                return user, "cached_ad"

        return None, "Authentication failed"

    async def _authenticate_ad_password(
        self, db: Session, username: str, password: str
    ) -> Optional[User]:
        """Явный логин через AD (пароль) с маппингом групп → роли."""
        if not self.ad_auth.is_available():
            return None
        if "\\" in username:
            domain_user = username
        else:
            domain_user = f"{self.ad_auth.domain}\\{username}"

        info = self.ad_auth.authenticate(username, password)
        if not info:
            return None

        # Поиск/автосоздание AD-пользователя в БД
        user = self.windows_auth.get_ad_user_from_db(domain_user, db)
        if user:
            user.last_login = datetime.utcnow()
            db.commit()
            return user

        if self.config.get("auth", {}).get("auto_create_ad_users", True):
            groups = info.get("groups", [])
            roles = self._map_groups_to_roles(groups, db)
            if not roles:
                roles = [self.config.get("auth", {}).get("default_role", "viewer")]

            user = User(
                username=info.get("username", username),
                email=info.get("email"),
                full_name=info.get("full_name", ""),
                domain_user=domain_user,
                auth_source="ad",
                is_active=True,
            )
            for role_name in roles:
                role = db.query(Role).filter(Role.name == role_name).first()
                if role:
                    user.roles.append(role)

            if not user.roles:
                default = (
                    db.query(Role)
                    .filter(Role.name == self.config.get("auth", {}).get("default_role", "viewer"))
                    .first()
                )
                if default:
                    user.roles.append(default)

            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created AD user via password login: %s", domain_user)
            return user

        return None

    async def _authenticate_ad_user(self, domain_user: str, db: Session) -> Optional[User]:
        """Аутентификация AD пользователя."""
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
                    email=user_info.get("email"),
                    full_name=user_info.get("full_name", ""),
                    domain_user=domain_user,
                    auth_source="ad",
                    is_active=True,
                )

                # Назначение ролей на основе AD групп
                groups = self.windows_auth.get_user_groups(domain_user)
                roles = self._map_groups_to_roles(groups, db)
                for role_name in roles:
                    role = db.query(Role).filter(Role.name == role_name).first()
                    if role:
                        user.roles.append(role)

                # Если ролей нет — добавляем default
                if not user.roles:
                    default = (
                        db.query(Role)
                        .filter(
                            Role.name == self.config.get("auth", {}).get("default_role", "viewer")
                        )
                        .first()
                    )
                    if default:
                        user.roles.append(default)

                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(
                    f"Created AD user: {domain_user} with roles: {[r.name for r in user.roles]}"
                )
                return user

        return None

    def _map_groups_to_roles(self, groups: list, db: Optional[Session] = None) -> list:
        """Маппинг AD групп на роли DCAP.

        Источники маппинга (по приоритету):
        1. Конфиг auth.windows_auth.group_mapping
        2. Поле Role.ad_group (заполняется в init_roles)
        """
        mapping = dict(self.config.get("auth", {}).get("windows_auth", {}).get("group_mapping", {}))
        roles = []
        for group in groups:
            mapped = mapping.get(group)
            if not mapped and db is not None:
                # Ищем роль по ad_group
                role = db.query(Role).filter(Role.ad_group == group).first()
                if role:
                    mapped = role.name
            if mapped:
                roles.append(mapped)
        return list(set(roles))
