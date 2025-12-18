from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Integer, String, Text

from app.db.base import Base


class Article(Base):
    """生成的公众号软文存储"""

    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True, comment="主键")
    title = Column(String(200), nullable=False, comment="标题/主题")
    summary = Column(String(500), nullable=True, comment="摘要/提示")
    content_md = Column(Text, nullable=False, comment="Markdown 格式内容")
    content_html = Column(Text, nullable=False, comment="HTML 格式内容，便于复制粘贴")
    source_refs = Column(JSON, nullable=True, comment="关联的数据源 ID 列表")

    # 生成链路持久化（便于排障、复用与审计）
    request_payload = Column(JSON, nullable=True, comment="生成请求参数（含模板/温度/长度等）")
    prompt_text = Column(Text, nullable=True, comment="最终发送给模型的 Prompt")

    # 素材包显式关联（便于统计与追溯）
    material_pack_id = Column(Integer, nullable=True, index=True, comment="素材包 ID")
    material_refs = Column(
        JSON,
        nullable=True,
        comment="素材引用结构化信息（item_ids/source_urls/source_event_ids/source_content_ids）",
    )

    template_key = Column(String(64), nullable=True, comment="使用的 Prompt 模板 key")
    template_version = Column(Integer, nullable=True, comment="使用的 Prompt 模板 version")
    llm_provider = Column(String(32), nullable=True, comment="模型供应商")
    llm_model = Column(String(64), nullable=True, comment="模型名称")
    elapsed_ms = Column(Integer, nullable=True, comment="生成耗时毫秒")
    usage = Column("usage", JSON, nullable=True, comment="token 用量等元信息", quote=True)

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
