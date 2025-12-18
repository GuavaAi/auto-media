from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from bs4 import BeautifulSoup


@dataclass
class ExtractResult:
    # 抽取后的正文文本（用于后续清洗/入库）
    main_text: str
    # 抽取方式：readability / bs4 / raw
    extractor: str
    # 可选元信息（例如标题）
    meta: Dict[str, Any]


def _looks_like_html(text: str) -> bool:
    if not text:
        return False
    t = text.lstrip().lower()
    if t.startswith("<!doctype") or t.startswith("<html"):
        return True
    return "<body" in t or "<div" in t or "<p" in t or "<article" in t


def extract_main_text(html_or_text: str, extractor_cfg: Optional[Dict[str, Any]] = None) -> ExtractResult:
    """从 HTML 中抽取正文文本。

    - 默认会尝试 readability（若依赖存在且文本看起来像 HTML）
    - readability 不可用或失败时，降级为 BeautifulSoup.get_text()
    - 若输入本身不是 HTML，则直接当纯文本处理
    """

    cfg = extractor_cfg or {}
    use_readability = cfg.get("use_readability")
    if use_readability is None:
        use_readability = True
    use_readability = bool(use_readability)

    raw = html_or_text or ""
    if not _looks_like_html(raw):
        return ExtractResult(main_text=raw, extractor="raw", meta={})

    # 先尝试 readability
    readability_error: str | None = None
    if use_readability:
        try:
            from readability import Document  # type: ignore

            doc = Document(raw)
            summary_html = doc.summary(html_partial=True)
            title = doc.short_title()
            text = BeautifulSoup(summary_html, "html.parser").get_text(
                separator="\n", strip=True
            )
            return ExtractResult(
                main_text=text,
                extractor="readability",
                meta={"title": title},
            )
        except Exception as exc:
            # 任何异常都降级到 bs4（避免因为依赖/解析问题影响抓取）
            readability_error = repr(exc)
            pass

    # bs4 兜底
    try:
        text = BeautifulSoup(raw, "html.parser").get_text(separator="\n", strip=True)
        meta: Dict[str, Any] = {}
        if readability_error:
            meta["readability_error"] = readability_error
        return ExtractResult(main_text=text, extractor="bs4", meta=meta)
    except Exception:
        return ExtractResult(main_text=raw, extractor="raw", meta={})
