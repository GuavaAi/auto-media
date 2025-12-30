from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.db.base import Base


class MaterialPack(Base):
    """素材包：承载一组可复用的素材条目（可混合多个事件/多个来源）。"""

    __tablename__ = "material_packs"

    id = Column(Integer, primary_key=True, index=True, comment="主键")

    # 中文说明：用于数据隔离。非管理员默认只能访问自己创建的素材包。
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="创建者用户 ID")

    name = Column(String(200), nullable=False, comment="素材包名称")
    description = Column(Text, nullable=True, comment="素材包描述")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
