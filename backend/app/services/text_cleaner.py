from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CleanResult:
    """清洗结果。

    说明：
    - clean_text：规则清洗后的正文
    - stats：统计信息，便于在抓取详情页展示与排障
    - quality_flags：质量标记，便于后续做告警/过滤
    - content_hash_clean：清洗后 hash，用于增量/去重
    """

    clean_text: str
    stats: Dict[str, Any]
    quality_flags: List[str]
    content_hash_clean: str


_DEFAULT_NOISE_KEYWORDS = [
    "免责声明",
    "版权声明",
    "本文来源",
    "转载",
    "上一篇",
    "下一篇",
    "相关阅读",
    "推荐阅读",
    "关注公众号",
    "扫码关注",
    "点击阅读原文",
    "阅读原文",
    "点赞",
    "在看",
    "分享",
    "收藏",
    "更多精彩",
    "返回顶部",
]


def _normalize_text(text: str) -> str:
    # 统一换行符、去掉首尾空白
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _split_lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.split("\n")]


def _compress_blank_lines(lines: List[str], max_blank: int = 2) -> List[str]:
    out: List[str] = []
    blank_run = 0
    for ln in lines:
        if ln == "":
            blank_run += 1
            if blank_run <= max_blank:
                out.append(ln)
            continue
        blank_run = 0
        out.append(ln)
    return out


def _dedupe_paragraphs(paragraphs: List[str]) -> Tuple[List[str], int]:
    seen = set()
    out: List[str] = []
    removed = 0
    for p in paragraphs:
        key = p.strip()
        if not key:
            continue
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        out.append(p)
    return out, removed


def clean_text(raw_text: str, cleaner_cfg: Optional[Dict[str, Any]] = None) -> CleanResult:
    """对正文做规则清洗（MVP）。

    设计目标：
    - 可回溯：输出统计信息与质量标记
    - 可配置：噪声关键词/短行阈值等可被 datasource.config 覆盖
    - 安全：宁可少删，避免误删关键内容
    """

    cfg = cleaner_cfg or {}

    noise_keywords = cfg.get("noise_keywords")
    if not isinstance(noise_keywords, list) or not noise_keywords:
        noise_keywords = list(_DEFAULT_NOISE_KEYWORDS)
    noise_keywords = [str(x) for x in noise_keywords if str(x).strip()]

    min_line_len = int(cfg.get("min_line_len", 6) or 6)
    min_text_len = int(cfg.get("min_text_len", 120) or 120)

    text = _normalize_text(raw_text or "")
    raw_len = len(text)

    # 拆行 -> 基于关键词与短行规则过滤
    lines = _split_lines(text)
    removed_by_keyword = 0
    removed_short_noise = 0

    filtered_lines: List[str] = []
    for ln in lines:
        if not ln:
            filtered_lines.append("")
            continue

        # 命中噪声关键词，直接过滤
        if any(k in ln for k in noise_keywords):
            removed_by_keyword += 1
            continue

        # 过短且疑似按钮/导航残留
        if len(ln) < min_line_len:
            # 纯符号/序号/分隔线
            if re.fullmatch(r"[-_=*·•.]{2,}", ln) or re.fullmatch(r"\d+", ln):
                removed_short_noise += 1
                continue

        filtered_lines.append(ln)

    filtered_lines = _compress_blank_lines(filtered_lines, max_blank=2)

    # 段落化（按空行切分）
    paragraphs: List[str] = []
    buf: List[str] = []
    for ln in filtered_lines:
        if ln == "":
            if buf:
                paragraphs.append("\n".join(buf).strip())
                buf = []
            continue
        buf.append(ln)
    if buf:
        paragraphs.append("\n".join(buf).strip())

    paragraphs, removed_dup_para = _dedupe_paragraphs(paragraphs)

    clean = "\n\n".join([p for p in paragraphs if p]).strip()
    clean_len = len(clean)

    # 计算 hash（清洗后）
    content_hash_clean = hashlib.md5(clean.encode("utf-8", "ignore")).hexdigest() if clean else ""

    # 质量标记：用于前端展示与后续过滤
    quality_flags: List[str] = []
    if clean_len < min_text_len:
        quality_flags.append("too_short")

    removed_total = removed_by_keyword + removed_short_noise + removed_dup_para
    if raw_len > 0:
        removed_ratio = min(1.0, removed_total / max(1, len(lines)))
        if removed_ratio >= 0.5:
            quality_flags.append("high_noise")

    stats: Dict[str, Any] = {
        "raw_len": raw_len,
        "clean_len": clean_len,
        "line_count": len(lines),
        "paragraph_count": len(paragraphs),
        "removed_by_keyword": removed_by_keyword,
        "removed_short_noise": removed_short_noise,
        "removed_dup_paragraph": removed_dup_para,
        "min_line_len": min_line_len,
        "min_text_len": min_text_len,
    }

    return CleanResult(
        clean_text=clean,
        stats=stats,
        quality_flags=quality_flags,
        content_hash_clean=content_hash_clean,
    )
