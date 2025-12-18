from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class PublishAccountCreate(BaseModel):
    name: str = Field(..., description="账号名称")
    provider: str = Field(..., description="平台标识，如 wechat_official")
    config: Dict[str, Any] = Field(..., description="平台配置 JSON（如 appid/secret）")


class PublishAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    provider: str
    is_active: bool
    config: Optional[Dict[str, Any]] = None
    created_at: datetime


class PublishTaskCreateDraftRequest(BaseModel):
    account_id: int = Field(..., description="发布账号 ID")
    article_id: int = Field(..., description="文章 ID")
    thumb_image_url: str = Field(..., description="封面图 URL（后端会下载并上传到公众号素材库，获取 thumb_media_id）")
    author: Optional[str] = Field(None, description="作者（可选）")
    digest: Optional[str] = Field(None, description="摘要（可选）")
    content_source_url: Optional[str] = Field(None, description="原文链接（可选）")


class PublishTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    action: str
    account_id: int
    article_id: Optional[int] = None
    status: str
    attempts: int
    max_attempts: int
    celery_task_id: Optional[str] = None
    next_retry_at: Optional[datetime] = None
    dlq: bool = False
    request: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    remote_id: Optional[str] = None
    remote_url: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
