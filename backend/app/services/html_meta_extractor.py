from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from bs4 import BeautifulSoup


@dataclass
class PageMeta:
    title: str | None
    publish_time: str | None
    modified_time: str | None
    raw: Dict[str, Any]


def _clean_text(s: str | None) -> str:
    return (s or "").strip()


def _safe_json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return None


def _walk_json(obj: Any) -> Iterable[Any]:
    if obj is None:
        return
    yield obj
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_json(v)


def _parse_datetime_to_iso(s: str | None) -> str | None:
    """尽可能把常见时间字符串解析为 ISO8601 字符串。

    中文说明：这里只做轻量解析，不引入 dateutil/dateparser。
    - 支持 ISO8601（含 Z/offset）
    - 支持常见 YYYY-MM-DD HH:MM(:SS)
    - 支持 YYYY/MM/DD
    - 支持中文 YYYY年MM月DD日 HH:MM
    """

    raw = _clean_text(s)
    if not raw:
        return None

    # 1) ISO8601
    try:
        iso = raw
        if iso.endswith("Z"):
            iso = iso[:-1] + "+00:00"
        dt = datetime.fromisoformat(iso)
        return dt.isoformat()
    except Exception:
        pass

    # 2) YYYY-MM-DD HH:MM(:SS)
    m = re.search(
        r"(?P<y>20\d{2})[-/\.](?P<m>\d{1,2})[-/\.](?P<d>\d{1,2})(?:\s+|T)?(?P<h>\d{1,2})?[:：]?(?P<mi>\d{1,2})?(?:[:：](?P<s>\d{1,2}))?",
        raw,
    )
    if m:
        try:
            y = int(m.group("y"))
            mo = int(m.group("m"))
            d = int(m.group("d"))
            hh = int(m.group("h") or 0)
            mm = int(m.group("mi") or 0)
            ss = int(m.group("s") or 0)
            return datetime(y, mo, d, hh, mm, ss).isoformat()
        except Exception:
            pass

    # 3) 中文 YYYY年MM月DD日 HH:MM
    m2 = re.search(
        r"(?P<y>20\d{2})年(?P<m>\d{1,2})月(?P<d>\d{1,2})日(?:\s*(?P<h>\d{1,2})[:：](?P<mi>\d{1,2})(?:[:：](?P<s>\d{1,2}))?)?",
        raw,
    )
    if m2:
        try:
            y = int(m2.group("y"))
            mo = int(m2.group("m"))
            d = int(m2.group("d"))
            hh = int(m2.group("h") or 0)
            mm = int(m2.group("mi") or 0)
            ss = int(m2.group("s") or 0)
            return datetime(y, mo, d, hh, mm, ss).isoformat()
        except Exception:
            pass

    return None


def extract_page_meta(html: str) -> PageMeta:
    """从 HTML 中提取标题、发布时间、更新时间等元信息。

    中文说明：
    - 这些字段是页面自身信息（meta/json-ld/time 标签），不是抓取时间。
    - 结果写入 DataSourceContent.extra，供后续“内容时间抽取/相对时间锚点”使用。
    """

    raw = html or ""
    soup = BeautifulSoup(raw, "html.parser")

    title = None
    try:
        title = _clean_text(soup.title.string if soup.title else None) or None
    except Exception:
        title = None

    # meta 标签候选
    meta_candidates: Dict[str, str] = {}
    for tag in soup.find_all("meta"):
        if not tag:
            continue
        key = _clean_text(tag.get("property") or tag.get("name") or tag.get("itemprop"))
        val = _clean_text(tag.get("content"))
        if not key or not val:
            continue
        meta_candidates[key.lower()] = val

    # time 标签候选
    time_tag_val = None
    ttag = soup.find("time")
    if ttag:
        time_tag_val = _clean_text(ttag.get("datetime")) or _clean_text(ttag.get_text())

    # JSON-LD 候选
    jsonld_vals: Dict[str, str] = {}
    for sc in soup.find_all("script"):
        if not sc:
            continue
        t = _clean_text(sc.get("type"))
        if t.lower() != "application/ld+json":
            continue
        payload = _safe_json_loads(_clean_text(sc.string) or _clean_text(sc.get_text()))
        if payload is None:
            continue
        for node in _walk_json(payload):
            if isinstance(node, dict):
                # 中文说明：JSON-LD 字段大小写/命名风格不统一，这里做大小写不敏感匹配
                for kk, vv in node.items():
                    if not isinstance(kk, str):
                        continue
                    low_k = kk.strip().lower()
                    if low_k in {"datepublished", "datemodified"}:
                        if isinstance(vv, str) and vv.strip():
                            jsonld_vals[low_k] = vv.strip()

    # 正文头部“发布时间/更新时间”文本候选
    text = soup.get_text("\n", strip=True)
    pub_text = None
    upd_text = None
    m_pub = re.search(r"(?:发布时间|发布于|发表时间|发稿时间)[:：\s]*([0-9]{4}[^\n]{0,30})", text)
    if m_pub:
        pub_text = _clean_text(m_pub.group(1))
    m_upd = re.search(r"(?:更新时间|更新于|最后更新)[:：\s]*([0-9]{4}[^\n]{0,30})", text)
    if m_upd:
        upd_text = _clean_text(m_upd.group(1))

    # 优先级选择
    publish_raw = (
        meta_candidates.get("article:published_time")
        or meta_candidates.get("og:published_time")
        or meta_candidates.get("publishdate")
        or meta_candidates.get("pubdate")
        or meta_candidates.get("timestamp")
        or meta_candidates.get("date")
        or jsonld_vals.get("datepublished")
        or pub_text
        or time_tag_val
    )

    modified_raw = (
        meta_candidates.get("article:modified_time")
        or meta_candidates.get("og:updated_time")
        or meta_candidates.get("last-modified")
        or jsonld_vals.get("datemodified")
        or upd_text
    )

    publish_time = _parse_datetime_to_iso(publish_raw)
    modified_time = _parse_datetime_to_iso(modified_raw)

    return PageMeta(
        title=title,
        publish_time=publish_time,
        modified_time=modified_time,
        raw={
            "title": title,
            "publish_time_raw": publish_raw,
            "publish_time": publish_time,
            "modified_time_raw": modified_raw,
            "modified_time": modified_time,
            "meta_candidates": meta_candidates,
            "jsonld": jsonld_vals,
            "time_tag": time_tag_val,
        },
    )
