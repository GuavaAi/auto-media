from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class PromptTemplateBase(BaseModel):
    name: Optional[str] = Field(None, description="模板名称（面向用户展示）")
    key: str = Field(..., description="模板标识")
    content: str = Field(..., description="模板内容（支持 {topic}/{outline}/{keywords}/{tone}/{length}/{summary_hint}/{sources} 占位）")


class PromptTemplateCreate(BaseModel):
    name: Optional[str] = Field(None, description="模板名称（面向用户展示）")
    key: Optional[str] = Field(None, description="模板标识（不传则自动生成）")
    content: str = Field(..., description="模板内容（支持 {topic}/{outline}/{keywords}/{tone}/{length}/{summary_hint}/{sources} 占位）")


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
