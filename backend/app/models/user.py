from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.db.base import Base


class User(Base):
    """系统用户，用于登录与权限控制"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    username = Column(String(50), unique=True, nullable=False, index=True, comment="登录用户名")
    full_name = Column(String(100), nullable=True, comment="显示姓名")
    email = Column(String(120), nullable=True, comment="邮箱")
    role = Column(String(20), nullable=False, default="editor", comment="角色：admin/editor")
    password_hash = Column(String(128), nullable=False, comment="密码哈希")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(
        DateTime,
        default=datetime.now,
        onupdate=datetime.now,
        nullable=False,
        comment="更新时间",
    )
