# manager/src/auth/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
import bcrypt

from manager.src.db.models import Base

# Таблица связи пользователей и ролей
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id")),
    Column("role_id", Integer, ForeignKey("roles.id")),
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
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

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
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200), nullable=True)
    ad_group = Column(String(100), nullable=True)  # AD-группа для маппинга (День 33)

    users = relationship("User", secondary=user_roles, back_populates="roles")

    def to_dict(self, with_count: bool = True) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "ad_group": self.ad_group,
        }
        if with_count:
            data["user_count"] = len(self.users)
        return data
