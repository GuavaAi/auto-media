from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.material import MaterialItemCreate


class CrawlRecordBase(BaseModel):
    datasource_id: int = Field(..., description="关联数据源 ID")
    datasource_name: Optional[str] = Field(None, description="数据源名称")
    source_type: str = Field(..., description="数据源类型")
    title: Optional[str] = Field(None, description="内容标题/来源标识")
    url: Optional[str] = Field(None, description="原始 URL（用于回溯与跳转）")
    content_preview: Optional[str] = Field(None, description="内容预览")
    extra: Optional[Dict[str, Any]] = Field(None, description="额外元信息")
    fetched_at: datetime = Field(..., description="抓取时间")


class CrawlRecordOut(CrawlRecordBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class CrawlRecordDetailOut(CrawlRecordOut):
    content: str = Field(..., description="抓取/读取到的原始文本内容")


class CrawlRecordQuickFetchRequest(BaseModel):
    url: str = Field(..., description="要抓取的 URL")
    crawler_engine: Optional[str] = Field(
        None,
        description="抓取引擎：requests/playwright/crawl4ai/firecrawl（可选，默认 requests）",
    )
    timeout: Optional[int] = Field(None, description="抓取超时（秒，可选）")
    use_playwright: Optional[bool] = Field(
        None,
        description="是否启用 Playwright（兼容旧用法；crawler_engine=playwright 时可忽略）",
    )
    css_selector: Optional[str] = Field(
        None,
        description="可选 CSS 选择器：用于从页面中选择特定元素区域抽取正文（例如 #content 或 article）",
    )


class CrawlRecordQuickFetchResponse(CrawlRecordOut):
    """快捷抓取结果（会写入抓取记录表并返回该条记录信息）。"""


class CrawlRecordQuickFetchPreviewRequest(BaseModel):
    url: str = Field(..., description="要抓取的 URL")
    crawler_engine: Optional[str] = Field(None, description="抓取引擎：requests/playwright/crawl4ai/firecrawl")
    timeout: Optional[int] = Field(None, description="抓取超时（秒，可选）")
    use_playwright: Optional[bool] = Field(None, description="是否启用 Playwright")
    css_selector: Optional[str] = Field(None, description="可选 CSS 选择器（预览抽取效果）")


class CrawlRecordQuickFetchPreviewResponse(BaseModel):
    url: str = Field(..., description="原始 URL")
    final_url: Optional[str] = Field(None, description="抓取后的最终 URL（如重定向）")
    status_code: Optional[int] = Field(None, description="HTTP 状态码")
    title: Optional[str] = Field(None, description="抽取到的标题")
    extractor: str = Field(..., description="正文抽取方式")
    text_preview: str = Field(..., description="抽取文本预览（截断）")


class CrawlRecordListResponse(BaseModel):
    total: int = Field(..., description="总数")
    limit: int = Field(..., description="分页大小")
    offset: int = Field(..., description="偏移量")
    items: List[CrawlRecordOut] = Field(..., description="列表数据")


class CrawlRecordExtractMaterialsRequest(BaseModel):
    top_k: int = Field(8, ge=1, le=50, description="返回条目数量（上限 50）")
    include_source: bool = Field(True, description="是否附带 source 类型条目（来源 URL/标题）")


class CrawlRecordExtractMaterialsResponse(BaseModel):
    items: List[MaterialItemCreate] = Field(..., description="可直接加入素材篮/写入素材包的条目列表")
