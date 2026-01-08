from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.llm_provider import get_provider


@dataclass
class TimeExtractResult:
    event_time_start: datetime | None
    event_time_end: datetime | None
    confidence: float
    signals: list[dict]
    used_llm: bool = False


def _try_parse_iso_datetime(s: str | None) -> datetime | None:
    raw = (s or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except Exception:
        return None


def _extract_absolute_datetimes(text: str) -> list[tuple[datetime, str]]:
    """从文本中抽取明确的绝对时间。

    中文说明：
    - 只实现常见格式，作为规则兜底
    - 抽取结果用于生成时间范围与供 LLM 兜底提供候选
    """

    out: list[tuple[datetime, str]] = []
    t = text or ""

    # 2026-01-07 10:30(:00)
    for m in re.finditer(
        r"(?P<y>20\d{2})[-/\.](?P<m>\d{1,2})[-/\.](?P<d>\d{1,2})(?:\s+|T)(?P<h>\d{1,2})[:：](?P<mi>\d{1,2})(?:[:：](?P<s>\d{1,2}))?",
        t,
    ):
        try:
            dt = datetime(
                int(m.group("y")),
                int(m.group("m")),
                int(m.group("d")),
                int(m.group("h")),
                int(m.group("mi")),
                int(m.group("s") or 0),
            )
            out.append((dt, m.group(0)))
        except Exception:
            pass

    # 2026年1月7日( 10:30)
    for m in re.finditer(
        r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日(?:\s*(?P<h>\d{1,2})[:：](?P<mi>\d{1,2})(?:[:：](?P<s>\d{1,2}))?)?",
        t,
    ):
        try:
            dt = datetime(
                int(m.group("y")),
                int(m.group("m")),
                int(m.group("d")),
                int(m.group("h") or 0),
                int(m.group("mi") or 0),
                int(m.group("s") or 0),
            )
            out.append((dt, m.group(0)))
        except Exception:
            pass

    return out


def _extract_relative_hints(text: str) -> list[str]:
    """抽取相对时间词（不做强解析，交给 LLM 或基于 anchor_time 处理）。"""

    t = text or ""
    hints: list[str] = []
    for w in [
        "刚刚",
        "刚才",
        "目前",
        "截至发稿",
        "今日",
        "今天",
        "昨晚",
        "昨日",
        "昨天",
        "今晨",
        "凌晨",
        "本周",
        "本月",
        "过去24小时",
        "过去 24 小时",
        "近24小时",
        "近 24 小时",
        "小时前",
        "分钟之前",
    ]:
        if w in t:
            hints.append(w)
    return hints


def _extract_first_json_obj(text: str) -> Optional[dict]:
    s = (text or "").strip()
    if not s:
        return None
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", s, flags=re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        chunk = s[start : end + 1]
        try:
            obj = json.loads(chunk)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


def extract_event_time_from_content(
    *,
    title: str | None,
    text: str,
    extra: dict | None,
    provider: str | None,
    db,
    allow_llm: bool = True,
) -> TimeExtractResult:
    """从抓取内容中抽取“事件发生时间范围”。

    中文说明：
    - 不使用 fetched_at 作为事件时间依据
    - 优先使用页面元信息 publish_time/modified_time 作为相对时间锚点
    - 规则能确定时直接返回；不确定时可选走 LLM 兜底
    """

    extra = extra if isinstance(extra, dict) else {}
    signals: list[dict] = []

    pub_iso = extra.get("publish_time")
    mod_iso = extra.get("modified_time")
    anchor_time = _try_parse_iso_datetime(mod_iso) or _try_parse_iso_datetime(pub_iso)
    if anchor_time:
        signals.append({"type": "anchor", "source": "page_meta", "value": anchor_time.isoformat()})

    # 候选文本：标题 + 前 1200 字正文（避免 prompt 太大）
    t = (text or "").strip()
    if len(t) > 1200:
        t = t[:1200]
    full = "\n".join([x for x in [(title or "").strip(), t] if x]).strip()

    abs_times = _extract_absolute_datetimes(full)
    if abs_times:
        abs_times.sort(key=lambda x: x[0])
        signals.append({"type": "abs_times", "count": len(abs_times), "samples": [x[1] for x in abs_times[:3]]})

        # 规则策略：若有 >=2 个绝对时间，取最小~最大作为范围；若只有 1 个，作为点时间
        start = abs_times[0][0]
        end = abs_times[-1][0]
        conf = 0.78 if len(abs_times) >= 2 else 0.68
        return TimeExtractResult(event_time_start=start, event_time_end=end, confidence=conf, signals=signals)

    # 若没有绝对时间，但有 anchor_time：对常见相对时间做非常轻量解析
    rel_hints = _extract_relative_hints(full)
    if rel_hints:
        signals.append({"type": "relative_hints", "hints": rel_hints[:8]})

    if anchor_time and rel_hints:
        # 简化规则：
        # - 今天/今日 -> anchor 日期
        # - 昨天/昨日 -> anchor -1天
        # - 刚刚/刚才/目前/截至发稿 -> 取 anchor
        day = anchor_time.date()
        if any(x in rel_hints for x in ["昨天", "昨日", "昨晚"]):
            day = (anchor_time - timedelta(days=1)).date()
        if any(x in rel_hints for x in ["今天", "今日", "今晨", "凌晨"]):
            day = anchor_time.date()
        # 只做日级别：返回 [day 00:00, day 23:59:59]
        start = datetime(day.year, day.month, day.day, 0, 0, 0)
        end = datetime(day.year, day.month, day.day, 23, 59, 59)
        return TimeExtractResult(event_time_start=start, event_time_end=end, confidence=0.55, signals=signals)

    if not allow_llm:
        return TimeExtractResult(event_time_start=None, event_time_end=None, confidence=0.0, signals=signals)

    # LLM 兜底：要求严格 JSON
    prompt_lines: list[str] = []
    prompt_lines.append("你是一个信息抽取助手。你的任务：从新闻/抓取文本中推断‘事件发生的时间范围’。")
    prompt_lines.append("注意：不要使用抓取时间作为依据；可以使用文章自身的发布时间/更新时间作为相对时间锚点。")
    if anchor_time:
        prompt_lines.append(f"【文章锚点时间（发布时间/更新时间）】{anchor_time.isoformat()}")
    prompt_lines.append("请严格只输出 JSON，不要输出任何多余文字。")
    prompt_lines.append("\n【输入】")
    prompt_lines.append(full)
    prompt_lines.append(
        "\n【输出 JSON 规范】\n"
        "{\n"
        "  \"event_time_start\": \"YYYY-MM-DD HH:MM:SS\" | null,\n"
        "  \"event_time_end\": \"YYYY-MM-DD HH:MM:SS\" | null,\n"
        "  \"confidence\": 0.0,\n"
        "  \"reason\": \"...\"\n"
        "}\n"
        "要求：\n"
        "- confidence 范围 0~1\n"
        "- 如果无法判断，event_time_start/end 输出 null，confidence 设为 0\n"
    )

    provider_impl = get_provider(provider, db=db)
    raw = provider_impl.generate("\n".join(prompt_lines), temperature=0.1, length=900)
    obj = _extract_first_json_obj(raw)
    if not obj:
        signals.append({"type": "llm", "ok": False, "raw_head": raw[:200]})
        return TimeExtractResult(event_time_start=None, event_time_end=None, confidence=0.0, signals=signals, used_llm=True)

    def _parse_dt_field(v: Any) -> datetime | None:
        if v is None:
            return None
        if isinstance(v, str) and v.strip():
            s2 = v.strip()
            # 兼容 YYYY-MM-DD HH:MM:SS
            try:
                if "T" in s2:
                    return datetime.fromisoformat(s2)
                return datetime.strptime(s2, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    return datetime.fromisoformat(s2)
                except Exception:
                    return None
        return None

    start = _parse_dt_field(obj.get("event_time_start"))
    end = _parse_dt_field(obj.get("event_time_end"))
    try:
        conf = float(obj.get("confidence") or 0.0)
    except Exception:
        conf = 0.0
    reason = obj.get("reason")
    signals.append({"type": "llm", "ok": True, "reason": reason})

    return TimeExtractResult(event_time_start=start, event_time_end=end, confidence=max(0.0, min(1.0, conf)), signals=signals, used_llm=True)
