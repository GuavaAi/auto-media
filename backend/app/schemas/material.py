from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class MaterialPackCreate(BaseModel):
    name: str = Field(..., description="素材包名称")
    description: Optional[str] = Field(None, description="素材包描述")


class MaterialPackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime


class MaterialPackListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[MaterialPackOut]


class MaterialItemCreate(BaseModel):
    item_type: str = Field(..., description="bullet/quote/fact/source/note")
    text: str = Field(..., description="素材内容")
    source_url: Optional[str] = Field(None, description="来源链接")
    source_content_id: Optional[int] = Field(None, description="关联采集内容 ID")
    source_event_id: Optional[int] = Field(None, description="关联热点事件 ID")
    meta: Optional[Dict[str, Any]] = Field(None, description="扩展字段")


class MaterialItemUpdate(BaseModel):
    item_type: Optional[str] = None
    text: Optional[str] = None
    source_url: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class MaterialItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pack_id: int
    item_type: str
    text: str
    text_hash: str
    source_url: Optional[str] = None
    source_content_id: Optional[int] = None
    source_event_id: Optional[int] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class MaterialPackDetailResponse(BaseModel):
    pack: MaterialPackOut
    items: List[MaterialItemOut]


class MaterialItemBatchCreateRequest(BaseModel):
    items: List[MaterialItemCreate]


class MaterialItemSearchResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[MaterialItemOut]


class DedupeResponse(BaseModel):
    removed: int


class FirecrawlSearchIngestRequest(BaseModel):
    query: str = Field(..., description="Firecrawl 搜索 query")
    limit: int = Field(10, ge=1, le=100, description="返回条数（1~100）")
    tbs: Optional[str] = Field(None, description="时间范围，例如 qdr:d/qdr:w/cdr:1,cd_min:...")
    sources: Optional[List[str]] = Field(None, description="搜索来源，默认 ['web']")
    api_key: Optional[str] = Field(None, description="可选：Firecrawl API Key，留空则使用服务端环境变量")
    api_base: Optional[str] = Field(None, description="可选：Firecrawl Base URL，默认官方 https://api.firecrawl.dev/v1")


class FirecrawlSearchIngestResponse(BaseModel):
    ingested: int = Field(..., description="成功入库条数")
    skipped: int = Field(..., description="去重/无内容等跳过条数")
    items: List[MaterialItemCreate] = Field(..., description="可直接加入素材篮的条目列表")


class AliyunUnifiedSearchIngestRequest(BaseModel):
    query: str = Field(..., description="搜索问题（1~500 字符）")
    engine_type: Optional[str] = Field(
        "Generic",
        description="搜索引擎类型：Generic/GenericAdvanced",
    )
    time_range: Optional[str] = Field(
        "NoLimit",
        description="时间范围：OneDay/OneWeek/OneMonth/OneYear/NoLimit",
    )
    category: Optional[str] = Field(
        None,
        description="可选：查询分类（finance/law/medical/internet/tax/news_province/news_center），多个用逗号分隔",
    )
    location: Optional[str] = Field(None, description="可选：位置信息（目前支持 IP）")
    include_main_text: bool = Field(True, description="是否请求返回 mainText（正文，最大约 3000 字符）")
    advanced_params: Optional[Dict[str, str]] = Field(
        None,
        description="可选：高级检索参数（例如 startPublishedDate/endPublishedDate，格式 YYYY-MM-DD）",
    )


class AliyunUnifiedSearchIngestResponse(BaseModel):
    ingested: int = Field(..., description="成功入库条数")
    skipped: int = Field(..., description="去重/无内容等跳过条数")
    items: List[MaterialItemCreate] = Field(..., description="可直接加入素材篮的条目列表")
