from __future__ import annotations

from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.prompt_template import PromptTemplate


DEFAULT_TEMPLATE_KEY = "default_article"
DEFAULT_TEMPLATE_VERSION = 1

# 默认/内置模板：允许使用但不允许删除（避免误删导致生成链路不可用）
BUILTIN_TEMPLATE_KEYS = {
    "copywriting.basic.v1",
    "copywriting.story.v1",
    "copywriting.product.v1",
    "copywriting.hotspot.v1",
}

PROTECTED_TEMPLATE_KEYS = {DEFAULT_TEMPLATE_KEY, *BUILTIN_TEMPLATE_KEYS}

DEFAULT_TEMPLATE_CONTENT = """你是一名资深新媒体编辑，请根据要求写一篇适合公众号的软文。
写作要求：
- 语气：{tone}
- 目标字数：约 {length} 字
- 使用 Markdown 二级/三级标题分段，突出重点，可以使用列表与加粗。
- 开头用 2~3 句话快速点题与利益点，结尾给出行动号召（如关注/收藏/私信）。
- 若提供大纲，需覆盖大纲要点；若提供关键词，请融入正文。
- 如引用来源信息，请用自然语言融合，不要直接堆砌。

主题：{topic}
大纲：
{outline}

关键词：{keywords}
补充视角：{summary_hint}

可用素材（可选，优先使用）：
{materials}

参考来源（可选）：
{sources}
"""


def get_latest_template(db: Session, key: str) -> Optional[PromptTemplate]:
    return (
        db.query(PromptTemplate)
        .filter(PromptTemplate.key == key)
        .order_by(desc(PromptTemplate.version), desc(PromptTemplate.id))
        .first()
    )


def get_template(db: Session, key: str, version: int | None = None) -> Optional[PromptTemplate]:
    if version is None:
        return get_latest_template(db, key)
    return (
        db.query(PromptTemplate)
        .filter(PromptTemplate.key == key, PromptTemplate.version == version)
        .first()
    )


def ensure_default_template(db: Session) -> PromptTemplate:
    """确保默认模板存在（便于无管理界面时也能直接使用模板能力）。"""

    existing = get_template(db, DEFAULT_TEMPLATE_KEY, DEFAULT_TEMPLATE_VERSION)
    if existing:
        return existing

    tpl = PromptTemplate(
        key=DEFAULT_TEMPLATE_KEY,
        version=DEFAULT_TEMPLATE_VERSION,
        content=DEFAULT_TEMPLATE_CONTENT,
    )
    db.add(tpl)
    db.flush()
    return tpl


def is_protected_template_key(key: str) -> bool:
    """判断是否为受保护模板（默认/内置模板不可删除）。"""

    return key in PROTECTED_TEMPLATE_KEYS


def delete_templates_by_key(db: Session, key: str) -> int:
    """按 key 删除该模板的全部版本。

    返回：实际删除的行数。
    """

    deleted = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.key == key)
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


def create_new_template_version(db: Session, key: str, content: str) -> PromptTemplate:
    """创建某个模板 key 的新版本（version 自增）。"""

    latest = get_latest_template(db, key)
    next_version = int(latest.version) + 1 if latest else 1

    tpl = PromptTemplate(
        key=key,
        version=next_version,
        content=content,
    )
    db.add(tpl)
    db.flush()
    return tpl
