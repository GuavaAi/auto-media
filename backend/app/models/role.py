from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String

from app.db.base import Base


class Role(Base):
    """角色：用于控制可访问的菜单（前端）与接口权限（后端）"""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    key = Column(String(50), unique=True, nullable=False, index=True, comment="角色标识")
    name = Column(String(100), nullable=False, comment="角色名称")

    # 中文说明：存储该角色允许访问的菜单 key 列表（前端使用同一套 key）
    menus = Column(JSON, nullable=False, default=list, comment="菜单权限列表")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        comment="更新时间",
    )
