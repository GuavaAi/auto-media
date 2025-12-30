from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleBase(BaseModel):
    key: str = Field(..., min_length=2, max_length=50, description="角色标识")
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    menus: list[str] = Field(default_factory=list, description="可访问菜单 key 列表")


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    menus: list[str] | None = None


class RoleOut(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoleListResponse(BaseModel):
    total: int
    items: list[RoleOut]
