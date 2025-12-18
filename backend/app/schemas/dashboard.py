from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

class StatsResponse(BaseModel):
    total_articles: int
    today_articles: int
    total_crawl: int
    today_crawl: int
    total_datasources: int


class RecentArticle(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    elapsed_ms: Optional[int] = None
    created_at: datetime


class RecentCrawlRecord(BaseModel):
    id: int
    datasource_id: int
    datasource_name: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None
    fetched_at: datetime
    extra: Optional[Dict[str, Any]] = None


class DashboardRecentResponse(BaseModel):
    recent_articles: List[RecentArticle]
    recent_crawl_records: List[RecentCrawlRecord]
