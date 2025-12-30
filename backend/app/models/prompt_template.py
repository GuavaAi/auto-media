from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.db.base import Base


class PromptTemplate(Base):
    """Prompt 模板（用于生成链路模板化与版本化）"""

    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    name = Column(String(200), nullable=True, comment="模板名称（面向用户展示）")
    key = Column(String(64), nullable=False, comment="模板标识")
    version = Column(Integer, nullable=False, default=1, comment="模板版本")
    content = Column(Text, nullable=False, comment="模板内容（支持 {topic}/{outline}/{keywords}/{tone}/{length}/{summary_hint}/{sources} 占位）")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")

    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_prompt_templates_key_version"),
    )
