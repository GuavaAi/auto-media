from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class PromptTemplateBase(BaseModel):
    key: str = Field(..., description="模板标识")
    content: str = Field(..., description="模板内容（支持 {topic}/{outline}/{keywords}/{tone}/{length}/{summary_hint}/{sources} 占位）")


class PromptTemplateCreate(PromptTemplateBase):
    """创建模板：同 key 自动创建新版本。"""


class PromptTemplateOut(PromptTemplateBase):
    id: int
    version: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromptTemplateListResponse(BaseModel):
    items: list[PromptTemplateOut]


class PromptTemplateCreateResponse(BaseModel):
    item: PromptTemplateOut


class PromptTemplateGetResponse(BaseModel):
    item: PromptTemplateOut
