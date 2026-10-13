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
    email: Optional[str] = None
    password: str
    full_name: Optional[str] = None
    auth_source: str = "local"
    is_active: bool = True
    roles: List[str] = ["viewer"]


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    auth_source: Optional[str] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserRoleUpdate(BaseModel):
    roles: List[str]


class UserListResponse(BaseModel):
    items: List[dict]
    total: int
    limit: int
    offset: int


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    domain_user: Optional[str] = None
    auth_source: str
    roles: List[str]
    is_active: bool
    created_at: Optional[str] = None
    last_login: Optional[str] = None


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    ad_group: Optional[str] = None


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    ad_group: Optional[str] = None


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    ad_group: Optional[str] = None
    user_count: int = 0


class RoleListResponse(BaseModel):
    items: List[dict]
    total: int


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    # BUG-201 (v3.13.39): подтверждение нового пароля — защита от опечаток.
    confirm_password: Optional[str] = None
