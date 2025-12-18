from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text, Index
from sqlalchemy.dialects.mysql import LONGTEXT

from app.db.base import Base


class DataSourceContent(Base):
    """数据源采集到的原始内容存储表"""

    __tablename__ = "data_source_contents"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    datasource_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True, comment="关联数据源 ID")
    source_type = Column(String(50), nullable=False, comment="数据源类型，冗余便于查询")
    url = Column(String(2048), nullable=True, comment="原始 URL（用于增量判重与回溯）")
    url_hash = Column(String(32), nullable=True, index=True, comment="URL 的 md5（用于高效索引查询）")
    title = Column(String(255), nullable=True, comment="内容标题/来源标识，如 URL 或文件名")
    content = Column(Text().with_variant(LONGTEXT, "mysql"), nullable=False, comment="抓取/读取到的原始文本内容")
    extra = Column(JSON, nullable=True, comment="额外元信息，如状态码、请求参数、headers")
    fetched_at = Column(DateTime, default=datetime.now, nullable=False, comment="抓取时间")

    __table_args__ = (
        Index(
            "ix_dsc_ds_urlhash_fetched",
            "datasource_id",
            "url_hash",
            "fetched_at",
        ),
    )
