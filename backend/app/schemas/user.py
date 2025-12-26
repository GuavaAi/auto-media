from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="登录用户名")
    full_name: Optional[str] = Field(None, max_length=100, description="展示名称")
    email: Optional[str] = Field(None, max_length=120, description="邮箱")
    role: str = Field("editor", description="角色：admin/editor")
    is_active: bool = Field(True, description="是否启用")


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=64, description="登录密码")


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=100, description="展示名称")
    email: Optional[str] = Field(None, max_length=120, description="邮箱")
    role: Optional[str] = Field(None, description="角色：admin/editor")
    is_active: Optional[bool] = Field(None, description="是否启用")
    password: Optional[str] = Field(
        None, min_length=6, max_length=64, description="若填写则重置密码"
    )


class UserOut(BaseModel):
    id: int
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserListResponse(BaseModel):
    total: int
    items: list[UserOut]


class AuthLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=64)


class AuthLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AuthProfileResponse(BaseModel):
    user: UserOut
