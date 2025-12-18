from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ArticleBase(BaseModel):
    title: str = Field(..., description="文章标题/主题")
    summary: Optional[str] = Field(None, description="摘要或导语")
    content_md: str = Field(..., description="Markdown 格式内容")


class ArticleCreate(ArticleBase):
    source_refs: Optional[List[int]] = Field(None, description="来源数据源 ID 列表")
    content_html: str = Field(..., description="HTML 格式内容")


class ArticleOut(ArticleBase):
    id: int
    content_html: str
    source_refs: Optional[List[int]] = None
    request_payload: Optional[dict] = None
    prompt_text: Optional[str] = None

    material_pack_id: Optional[int] = None
    material_refs: Optional[dict] = None

    template_key: Optional[str] = None
    template_version: Optional[int] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    elapsed_ms: Optional[int] = None
    usage: Optional[dict] = None
    created_at: datetime

    class Config:
        orm_mode = True


class ArticleUpdate(BaseModel):
    """文章更新（软文管理：手工编辑保存）。"""

    title: Optional[str] = None
    summary: Optional[str] = None
    content_md: Optional[str] = None
    content_html: Optional[str] = None


class DeleteResponse(BaseModel):
    ok: bool = True


class ArticleAiEditRequest(BaseModel):
    """对已生成文章进行 AI 二次处理。

    说明：
    - 该接口默认仅返回生成结果，不自动覆盖原文；前端编辑页可预览后再调用 ArticleUpdate 保存。
    """

    action: str = Field(..., description="rewrite/continue/translate")
    selected_text: Optional[str] = Field(None, description="用户选中的文本片段（若存在则仅针对此片段处理）")

    provider: Optional[str] = Field(None, description="可选：指定模型供应商，留空则使用默认配置")
    temperature: Optional[float] = Field(None, description="可选：生成温度")
    max_tokens: Optional[int] = Field(None, description="可选：最大 token")
    length: Optional[int] = Field(None, description="可选：期望字数（用于部分 provider 的 token 估算）")

    instruction: Optional[str] = Field(None, description="可选：额外指令（重写/续写的风格或方向）")
    target_language: Optional[str] = Field(None, description="翻译目标语言，例如：中文/英文/日文")


class ArticleAiEditResponse(BaseModel):
    content_md: str
    content_html: str
    prompt_text: Optional[str] = None


class GenerationRequest(BaseModel):
    """生成请求体"""

    topic: str = Field(..., description="生成主题/标题提示")
    outline: Optional[List[str]] = Field(None, description="可选的大纲条目")
    keywords: Optional[List[str]] = Field(None, description="关键词")
    tone: Optional[str] = Field(None, description="语气，如：专业且亲和")
    length: Optional[int] = Field(800, description="期望字数")
    temperature: Optional[float] = Field(
        0.7, description="生成温度，范围 0~1，值越大越有创造性"
    )
    max_tokens: Optional[int] = Field(
        None, description="最大生成 token 数，不填则按字数估算"
    )
    call_to_action: Optional[str] = Field(None, description="行动号召语")
    sources: Optional[List[int]] = Field(None, description="引用的数据源 ID 列表")

    material_pack_id: Optional[int] = Field(
        None, description="可选素材包 ID（用于注入要点/引用/事实/来源等素材）"
    )
    material_item_ids: Optional[List[int]] = Field(
        None, description="可选：仅使用素材包中指定的条目 ID（为空则使用整个素材包）"
    )

    materials: Optional[str] = Field(
        None,
        description="内部字段：用于将素材包条目拼接成文本块注入 Prompt（前端无需传）",
        exclude=True,
    )
    summary_hint: Optional[str] = Field(
        None, description="摘要/角度提示，用于约束生成风格"
    )
    provider: Optional[str] = Field(
        None, description="模型供应商标识，留空则使用默认配置"
    )

    template_key: Optional[str] = Field(None, description="Prompt 模板 key（可选）")
    template_version: Optional[int] = Field(None, description="Prompt 模板版本（可选，不填则取最新）")

    source_event_id: Optional[int] = Field(
        None, description="可选：从热点事件直接生成（自动加载该事件的 items 作为素材）"
    )

    source_query: Optional[str] = Field(
        None, description="可选：实时搜索生成（Values: 搜索关键词）。若设置此字段，将覆盖 source_event_id"
    )
