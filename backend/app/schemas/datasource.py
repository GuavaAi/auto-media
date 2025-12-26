from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class DataSourceBase(BaseModel):
    name: str = Field(..., description="数据源名称")
    source_type: str = Field(..., description="数据源类型，如 url/api/document/n8n")
    config: Dict[str, Any] | None = Field(
        None, description="数据源配置，含 urls/api_url/doc_url/webhook 等"
    )
    biz_category: Optional[str] = Field(None, description="业务分类")
    schedule_cron: Optional[str] = Field(
        None, description="定时抓取 cron 表达式，如 0 */2 * * *"
    )
    enable_schedule: bool = Field(False, description="是否开启定时抓取")


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceUpdate(BaseModel):
    name: Optional[str] = Field(None, description="数据源名称")
    source_type: Optional[str] = Field(None, description="数据源类型")
    config: Dict[str, Any] | None = Field(
        None, description="数据源配置，含 urls/api_url/doc_url/webhook 等"
    )
    biz_category: Optional[str] = Field(None, description="业务分类")
    schedule_cron: Optional[str] = Field(None, description="定时 cron")
    enable_schedule: Optional[bool] = Field(None, description="是否开启定时抓取")


class DataSourceOut(DataSourceBase):
    id: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
