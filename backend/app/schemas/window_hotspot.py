from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WindowHotspotBuildRequest(BaseModel):
    window: str = Field(..., description="realtime|today|week|month|range")
    limit: int = Field(20, ge=1, le=200, description="榜单条数")
    provider: Optional[str] = Field(None, description="可选：模型供应商（用于低置信时间的兜底解析）")
    use_llm: bool = Field(False, description="是否允许在时间抽取低置信时调用 LLM 兜底")
    start_time: Optional[str] = Field(None, description="可选：自定义范围开始时间（ISO），与 end_time 成对使用")
    end_time: Optional[str] = Field(None, description="可选：自定义范围结束时间（ISO），与 start_time 成对使用")


class WindowHotspotItemOut(BaseModel):
    type: str
    text: str
    score: float = 0.0
    source_url: Optional[str] = None
    source_content_id: Optional[int] = None
    position: int = 0
    extra: Optional[Dict[str, Any]] = None


class WindowHotspotSourceOut(BaseModel):
    content_id: Optional[int] = None
    url: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None
    is_list_parent: bool = False
    time_confidence: float = 0.0
    event_time_end: Optional[str] = None


class WindowHotspotEventOut(BaseModel):
    window: str
    title: str
    summary: Optional[str] = None
    hot_score: float = 0.0
    event_time_start: Optional[str] = None
    event_time_end: Optional[str] = None

    source_count: int = 0
    uniq_url_cnt: int = 0
    uniq_domain_cnt: int = 0
    domain_penalty: float = 1.0
    recency: float = 1.0

    flags: Optional[Dict[str, bool]] = None
    extra: Optional[Dict[str, Any]] = None
    bullets: List[WindowHotspotItemOut] = []
    quotes: List[WindowHotspotItemOut] = []
    sources: List[WindowHotspotSourceOut] = []


class WindowHotspotListResponse(BaseModel):
    window: str
    items: List[WindowHotspotEventOut]


class WindowHotspotListSmartFilterRequest(BaseModel):
    window: str = Field(..., description="today|week|month|range")
    topic: str = Field(..., min_length=1, description="用户输入的主题/方向，例如‘AI’‘财经’‘新能源’")
    provider: Optional[str] = Field(None, description="可选：模型供应商，不填则使用系统默认")
    instruction: Optional[str] = Field(None, description="可选：额外筛选指令")
    limit: int = Field(50, ge=5, le=200, description="最多参与筛选的热点事件数量")
    temperature: float = Field(0.2, ge=0.0, le=1.0, description="模型温度，越低越稳定")
    start_time: Optional[str] = Field(None, description="可选：自定义范围开始时间（ISO），与 end_time 成对使用")
    end_time: Optional[str] = Field(None, description="可选：自定义范围结束时间（ISO），与 start_time 成对使用")


class WindowHotspotListSmartFilterDecision(BaseModel):
    event_key: str
    recommended: bool = Field(False, description="模型是否推荐")
    score: float = Field(0.0, description="相关性评分（0~1）")
    reason: Optional[str] = Field(None, description="推荐/不推荐原因")


class WindowHotspotListSmartFilterResponse(BaseModel):
    window: str
    topic: str
    recommended_event_keys: List[str] = Field(default_factory=list)
    decisions: List[WindowHotspotListSmartFilterDecision] = Field(default_factory=list)
