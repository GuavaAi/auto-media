from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DailyHotspotEventBase(BaseModel):
    day: date = Field(..., description="所属日期")
    title: str = Field(..., description="事件标题")
    summary: Optional[str] = Field(None, description="一句话摘要")
    hot_score: float = Field(0.0, description="热度评分")
    keywords: Optional[List[str]] = Field(None, description="关键词")


class DailyHotspotEventOut(DailyHotspotEventBase):
    id: int
    source_count: int = Field(0, description="来源文章数")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DailyHotspotSourceOut(BaseModel):
    id: int
    content_id: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    weight: float = 1.0

    model_config = ConfigDict(from_attributes=True)


class DailyHotspotItemOut(BaseModel):
    id: int
    type: str = Field(..., description="bullet|quote|fact")
    text: str
    source_url: Optional[str] = None
    source_content_id: Optional[int] = None
    position: int = 0
    score: float = 0.0
    extra: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class DailyHotspotListResponse(BaseModel):
    day: date
    items: List[DailyHotspotEventOut]


class DailyHotspotDetailResponse(BaseModel):
    event: DailyHotspotEventOut
    bullets: List[DailyHotspotItemOut]
    quotes: List[DailyHotspotItemOut]
    facts: List[DailyHotspotItemOut]
    sources: List[DailyHotspotSourceOut]


class DailyHotspotSmartFilterRequest(BaseModel):
    provider: Optional[str] = Field(None, description="可选：模型供应商，不填则使用系统默认")
    instruction: Optional[str] = Field(None, description="可选：筛选指令，例如‘更偏财经/AI/科技’")
    include_types: Optional[List[str]] = Field(None, description="可选：参与筛选的类型 bullet/quote/fact")
    max_items: int = Field(30, ge=5, le=200, description="最多参与筛选的条目数量")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="模型温度，越低越稳定")


class DailyHotspotSmartFilterDecision(BaseModel):
    id: int
    type: str
    recommended: bool = Field(False, description="模型是否推荐")
    score: float = Field(0.0, description="相关性评分（0~1）")
    reason: Optional[str] = Field(None, description="推荐/不推荐原因")


class DailyHotspotSmartFilterResponse(BaseModel):
    event_id: int
    recommended_item_ids: List[int] = Field(default_factory=list)
    decisions: List[DailyHotspotSmartFilterDecision] = Field(default_factory=list)


class DailyHotspotListSmartFilterRequest(BaseModel):
    day: date = Field(..., description="日期 YYYY-MM-DD")
    topic: str = Field(..., min_length=1, description="用户输入的主题/方向，例如‘AI’‘财经’‘新能源’")
    provider: Optional[str] = Field(None, description="可选：模型供应商，不填则使用系统默认")
    instruction: Optional[str] = Field(None, description="可选：额外筛选指令")
    limit: int = Field(50, ge=5, le=200, description="最多参与筛选的热点事件数量")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="模型温度，越低越稳定")


class DailyHotspotListSmartFilterDecision(BaseModel):
    event_id: int
    recommended: bool = Field(False, description="模型是否推荐")
    score: float = Field(0.0, description="相关性评分（0~1）")
    reason: Optional[str] = Field(None, description="推荐/不推荐原因")


class DailyHotspotListSmartFilterResponse(BaseModel):
    day: date
    topic: str
    recommended_event_ids: List[int] = Field(default_factory=list)
    decisions: List[DailyHotspotListSmartFilterDecision] = Field(default_factory=list)
