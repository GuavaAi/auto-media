from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    provider: str = Field(..., description="服务标识，如 firecrawl")
    name: Optional[str] = Field(None, description="名称/备注")
    key: str = Field(..., description="API Key")
    is_active: bool = Field(True, description="是否启用")
    extra: Optional[Dict[str, Any]] = Field(None, description="扩展配置（如 Azure endpoint/deployment/api_version）")


class ApiKeyUpdate(BaseModel):
    name: Optional[str] = None
    key: Optional[str] = None
    is_active: Optional[bool] = None
    extra: Optional[Dict[str, Any]] = None


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    name: Optional[str] = None
    is_active: bool
    last_used_at: Optional[datetime] = None
    use_count: int
    created_at: datetime
    updated_at: datetime
    key_masked: str = ""
    extra: Optional[Dict[str, Any]] = None


class ApiKeyListResponse(BaseModel):
    total: int
    items: List[ApiKeyOut]


class ApiKeyPickRequest(BaseModel):
    provider: str = Field(..., description="服务标识，如 firecrawl")


class ApiKeyPickResponse(BaseModel):
    id: int
    provider: str
    key: str
    name: Optional[str] = None
    last_used_at: Optional[datetime] = None
    use_count: int
    extra: Optional[Dict[str, Any]] = None
