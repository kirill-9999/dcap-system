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
    roles: List[str] = ["viewer"]


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


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
