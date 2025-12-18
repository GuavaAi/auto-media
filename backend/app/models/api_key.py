from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, Index, JSON

from app.db.base import Base


class ApiKey(Base):
    """第三方 API Key 池。

    用途：统一管理外部服务（例如 firecrawl）的多把 key，调用时自动轮询/最久未用优先选取。
    """

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    provider = Column(String(64), nullable=False, index=True, comment="服务标识，如 firecrawl")

    # 方便人工识别（例如：firecrawl-1、firecrawl-备用）
    name = Column(String(128), nullable=True, comment="名称/备注")

    # 直接保存 key（如需更高安全性可后续改为加密存储）
    key = Column(Text, nullable=False, comment="API Key")

    # 扩展配置（用于 Azure/OpenAI 等场景，如 endpoint/deployment/api_version/base_url/model）
    extra = Column(JSON, nullable=True, comment="扩展配置")

    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    last_used_at = Column(DateTime, nullable=True, comment="最近一次被选取使用的时间")
    use_count = Column(Integer, default=0, nullable=False, comment="累计使用次数")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False, comment="更新时间")

    __table_args__ = (
        Index("ix_api_keys_provider_active_lastused", "provider", "is_active", "last_used_at"),
    )
