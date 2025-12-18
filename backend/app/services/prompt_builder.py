from typing import List, Optional

from app.core.config import get_settings
from app.schemas.article import GenerationRequest


def render_prompt(template: str, variables: dict) -> str:
    """渲染 Prompt 模板。

    采用 str.format_map，未提供的字段会保留为空字符串，避免 KeyError。
    """

    class _SafeDict(dict):
        def __missing__(self, key: str) -> str:
            return ""

    return (template or "").format_map(_SafeDict(**(variables or {}))).strip()


def build_generation_prompt(
    req: GenerationRequest, source_snippets: Optional[List[str]] = None
) -> str:
    """
    构建软文生成 Prompt，尽量约束风格和格式，方便后续直接用于公众号排版。
    """
    settings = get_settings()
    tone = req.tone or settings.GENERATION_TONE
    length = req.length or settings.GENERATION_LENGTH
    outline = "\n".join(f"- {item}" for item in req.outline or [])
    keywords = ", ".join(req.keywords or [])
    sources = "\n".join(source_snippets or [])
    materials = getattr(req, "materials", None)

    prompt = f"""
你是一名资深新媒体编辑，请根据要求写一篇适合公众号的软文。
写作要求：
- 语气：{tone}
- 目标字数：约 {length} 字
- 使用 Markdown 二级/三级标题分段，突出重点，可以使用列表与加粗。
- 开头用 2~3 句话快速点题与利益点，结尾给出行动号召（如关注/收藏/私信）。
- 若提供大纲，需覆盖大纲要点；若提供关键词，请融入正文。
- 如引用来源信息，请用自然语言融合，不要直接堆砌。

主题：{req.topic}
大纲：
{outline or '（无）'}

关键词：{keywords or '（无）'}
补充视角：{req.summary_hint or '（无）'}

可用素材（可选，优先使用）：
{materials or '（无）'}

参考来源（可选）：
{sources or '（无）'}
"""
    return prompt.strip()


def build_generation_prompt_with_template(
    req: GenerationRequest,
    template: str,
    source_snippets: Optional[List[str]] = None,
) -> str:
    """使用自定义模板构建 Prompt。"""

    settings = get_settings()
    tone = req.tone or settings.GENERATION_TONE
    length = req.length or settings.GENERATION_LENGTH
    outline = "\n".join(f"- {item}" for item in req.outline or [])
    keywords = ", ".join(req.keywords or [])
    sources = "\n".join(source_snippets or [])
    materials = getattr(req, "materials", None)

    variables = {
        "topic": req.topic,
        "outline": outline or "（无）",
        "keywords": keywords or "（无）",
        "tone": tone,
        "length": length,
        "summary_hint": req.summary_hint or "（无）",
        "materials": materials or "（无）",
        "sources": sources or "（无）",
    }
    return render_prompt(template, variables)
