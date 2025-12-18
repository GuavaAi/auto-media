from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, Index

from app.db.base import Base


class MaterialItem(Base):
    """素材条目：bullet/quote/fact/source/note 等，可混合来源并支持编辑。"""

    __tablename__ = "material_items"

    id = Column(Integer, primary_key=True, index=True, comment="主键")

    pack_id = Column(
        Integer,
        ForeignKey("material_packs.id"),
        nullable=False,
        index=True,
        comment="所属素材包 ID",
    )

    item_type = Column(
        String(32),
        nullable=False,
        index=True,
        comment="条目类型：bullet/quote/fact/source/note",
    )

    text = Column(Text, nullable=False, comment="素材内容")
    text_hash = Column(String(32), nullable=False, index=True, comment="用于去重的文本 hash")

    source_url = Column(String(2048), nullable=True, comment="来源链接（可选）")
    source_content_id = Column(Integer, nullable=True, index=True, comment="关联采集内容 ID（可选）")
    source_event_id = Column(Integer, nullable=True, index=True, comment="关联热点事件 ID（可选）")

    meta = Column(JSON, nullable=True, comment="扩展字段，如 score/weight/day 等")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    __table_args__ = (
        Index("ix_material_items_pack_type", "pack_id", "item_type"),
    )
