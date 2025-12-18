from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String

from app.db.base import Base


class PublishAccount(Base):
    """发布账号配置：用于不同平台（provider）的认证信息与配置。

    中文说明：
    - provider 用于区分平台（当前先支持 wechat_official）。
    - config 存放平台特定配置（如 appid/secret），后续可扩展为引用 APIKey 池等。
    """

    __tablename__ = "publish_accounts"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    name = Column(String(200), nullable=False, comment="账号名称")
    provider = Column(String(50), nullable=False, index=True, comment="平台标识，如 wechat_official")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    config = Column(JSON, nullable=True, comment="平台配置 JSON（appid/secret 等）")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
