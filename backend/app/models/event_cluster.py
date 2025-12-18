from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, Index
from sqlalchemy.dialects.mysql import LONGTEXT

from app.db.base import Base


class EventCluster(Base):
    """每日热点事件簇（按天聚合）"""

    __tablename__ = "event_clusters"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    day = Column(Date, nullable=False, index=True, comment="所属日期")

    title = Column(String(255), nullable=False, comment="事件标题")
    summary = Column(Text, nullable=True, comment="一句话摘要")
    hot_score = Column(Float, nullable=False, default=0.0, comment="热度评分")

    keywords = Column(JSON, nullable=True, comment="关键词列表")
    extra = Column(JSON, nullable=True, comment="扩展字段")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    __table_args__ = (
        Index("ix_event_clusters_day_hotscore", "day", "hot_score"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )


class EventClusterSource(Base):
    """事件簇关联的来源文章（多来源聚合）"""

    __tablename__ = "event_cluster_sources"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    event_id = Column(Integer, ForeignKey("event_clusters.id"), nullable=False, index=True, comment="事件簇ID")

    content_id = Column(Integer, ForeignKey("data_source_contents.id"), nullable=True, index=True, comment="来源抓取记录ID")
    url = Column(String(2048), nullable=True, comment="来源URL")
    title = Column(String(255), nullable=True, comment="来源标题")

    weight = Column(Float, nullable=False, default=1.0, comment="来源权重")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )


class EventClusterItem(Base):
    """事件簇条目（要点/引用/事实）"""

    __tablename__ = "event_cluster_items"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    event_id = Column(Integer, ForeignKey("event_clusters.id"), nullable=False, index=True, comment="事件簇ID")

    # bullet | quote | fact
    type = Column(String(32), nullable=False, index=True, comment="条目类型")
    text = Column(Text().with_variant(LONGTEXT, "mysql"), nullable=False, comment="内容")

    source_url = Column(String(2048), nullable=True, comment="引用来源URL")
    source_content_id = Column(Integer, ForeignKey("data_source_contents.id"), nullable=True, index=True, comment="引用来源抓取记录ID")

    position = Column(Integer, nullable=False, default=0, comment="排序")
    score = Column(Float, nullable=False, default=0.0, comment="条目评分")

    extra = Column(JSON, nullable=True, comment="扩展字段")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    __table_args__ = (
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
