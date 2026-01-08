from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent
from app.services.content_time_extractor import extract_event_time_from_content
from app.services.datasource_config_utils import is_list_page_datasource, is_subpage_record
from app.services.daily_hotspot_builder import (
    _dedupe_docs,
    _jaccard,
    _pick_bullets,
    _pick_quotes,
    _shingles,
    _truncate_text,
    _url_domain,
)


@dataclass
class _Doc:
    content_id: int
    datasource_id: int
    url: str | None
    title: str
    text: str
    fetched_at: datetime

    title_shingles: set[str]

    event_time_start: datetime | None
    event_time_end: datetime | None
    time_confidence: float

    # 中文说明：列表页父页面（聚合页）若进入窗口热点，属于策略B兜底；默认（策略A）应被过滤
    is_list_parent: bool = False


def _looks_like_detail_url(url: str | None) -> bool:
    u = (url or "").strip().lower()
    if not u:
        return False

    # 中文说明：一些站点的详情页路径相对稳定，这里做轻量兜底判断
    for seg in ["/details/", "/detail/", "/infomation/details/"]:
        if seg in u:
            return True
    return False


def _to_local_naive(dt: datetime | None) -> datetime | None:
    """将 datetime 统一转换为本地时区的 naive datetime。

    中文说明：
    - MySQL/业务侧通常以本地时间展示；窗口计算也是基于本地 now
    - 但页面元信息可能带 Z 或 offset，解析后得到 aware datetime
    - 这里统一转为本地时区，再去 tzinfo，避免 naive/aware 不能比较
    """

    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt
    local_tz = datetime.now().astimezone().tzinfo
    try:
        return dt.astimezone(local_tz).replace(tzinfo=None)
    except Exception:
        return dt.replace(tzinfo=None)


def _try_parse_iso_datetime(s: str | None) -> datetime | None:
    """解析 ISO 时间字符串。

    中文说明：
    - 兼容带 Z 的格式
    - 兼容仅日期 YYYY-MM-DD
    - 解析失败返回 None
    """

    raw = (s or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except Exception:
        pass
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            d = datetime.strptime(raw, "%Y-%m-%d")
            return d
        except Exception:
            return None
    return None


def _try_parse_relative_time_delta(text: str) -> timedelta | None:
    """从文本中识别“相对时间”（如 23小时前/10分钟前/刚刚）。

    中文说明：
    - 这类信息在资讯站点列表页很常见（例如“23小时前”）
    - 如果不处理，会导致 event_time_end 抽取失败 -> no_event_time -> 被窗口热点过滤
    - 这里仅做轻量规则，作为兜底，不追求覆盖所有复杂表达
    """

    t = (text or "").strip()
    if not t:
        return None

    if "刚刚" in t or "刚才" in t:
        return timedelta(minutes=1)

    if "前天" in t:
        return timedelta(days=2)

    if "昨天" in t or "昨日" in t:
        return timedelta(days=1)

    m = re.search(r"(\d{1,3})\s*小时\s*前", t)
    if m:
        try:
            h = int(m.group(1))
            return timedelta(hours=max(0, h))
        except Exception:
            return None

    m = re.search(r"(\d{1,4})\s*分钟\s*前", t)
    if m:
        try:
            mm = int(m.group(1))
            return timedelta(minutes=max(0, mm))
        except Exception:
            return None

    m = re.search(r"(\d{1,3})\s*天\s*前", t)
    if m:
        try:
            dd = int(m.group(1))
            return timedelta(days=max(0, dd))
        except Exception:
            return None

    return None


def _infer_year_for_month_day(*, base: datetime, month: int, day: int) -> int:
    """基于 base 推断月日的年份。

    中文说明：
    - 资讯站点经常只给“01-06 / 1月6日”
    - 默认用 base.year；若推断日期落在 base 之后（未来），则回退一年
    """

    year = int(base.year)
    try:
        dt = datetime(year, month, day, 0, 0, 0)
    except Exception:
        return year
    if dt > base:
        return year - 1
    return year


def _try_parse_date_from_mixed_text(*, text: str, base: datetime) -> datetime | None:
    """从标题/正文/URL 等混合文本中解析日期（作为 event_time_end 兜底）。

    支持：
    - yy-mm-dd（如 26-01-06，默认映射为 2026-01-06）
    - mm-dd（如 01-06）
    - m月d日（如 1月6日）
    """

    t = (text or "").strip()
    if not t:
        return None

    # 1) yy-mm-dd（常见于 URL: /issues/26-01-06-xxx）
    m = re.search(r"(?<!\d)(\d{2})-(\d{2})-(\d{2})(?!\d)", t)
    if m:
        try:
            yy = int(m.group(1))
            mm = int(m.group(2))
            dd = int(m.group(3))
            year = 2000 + yy
            return datetime(year, mm, dd, 0, 0, 0)
        except Exception:
            pass

    # 2) m月d日
    m = re.search(r"(?<!\d)(\d{1,2})\s*月\s*(\d{1,2})\s*日(?!\d)", t)
    if m:
        try:
            mm = int(m.group(1))
            dd = int(m.group(2))
            year = _infer_year_for_month_day(base=base, month=mm, day=dd)
            return datetime(year, mm, dd, 0, 0, 0)
        except Exception:
            pass

    # 3) mm-dd（避免匹配到 yy-mm-dd 的前两段，因此先尝试了 yy-mm-dd）
    m = re.search(r"(?<!\d)(\d{1,2})-(\d{1,2})(?!-\d)", t)
    if m:
        try:
            mm = int(m.group(1))
            dd = int(m.group(2))
            year = _infer_year_for_month_day(base=base, month=mm, day=dd)
            return datetime(year, mm, dd, 0, 0, 0)
        except Exception:
            pass

    return None


def _window_range(
    window: str,
    *,
    now: datetime,
    start_time: str | None = None,
    end_time: str | None = None,
) -> tuple[datetime, datetime, int]:
    """计算窗口起止与候选检索 lookback 天数。

    中文说明：
    - 窗口判断依据必须是内容抽取出来的 event_time
    - 但为了避免全表扫描，这里用 fetched_at 做“候选集合检索加速”（不作为事件时间依据）
    """

    w = (window or "").strip().lower()
    end = now

    if w in {"range", "custom"}:
        st = _try_parse_iso_datetime(start_time)
        et = _try_parse_iso_datetime(end_time)
        if not st or not et:
            raise ValueError("window=range 时必须同时传 start_time 与 end_time（ISO）")
        if st > et:
            raise ValueError("start_time 不能晚于 end_time")
        start = _to_local_naive(st)
        end = _to_local_naive(et)
        # 中文说明：范围越大候选回溯越大，但做上限保护避免全表扫描
        delta_days = max(1, int((end - start).total_seconds() / 86400.0) + 1)
        lookback_days = max(14, min(365, delta_days + 30))
        return start, end, lookback_days

    if w in {"realtime", "rt", "real"}:
        start = _to_local_naive(now - timedelta(hours=6))
        # 中文说明：实时窗口虽然只看最近几小时的“事件时间”，
        # 但抓取时间可能更早（例如历史抓取文章里提到“今天10:30发生”）。
        # 为避免漏选，这里扩大候选回溯范围。
        lookback_days = 14
        return start, _to_local_naive(end), lookback_days

    if w in {"today", "daily", "day"}:
        d = (now - timedelta(days=1)).date()
        start = _to_local_naive(datetime(d.year, d.month, d.day, 0, 0, 0))
        lookback_days = 21
        return start, _to_local_naive(end), lookback_days

    if w in {"week", "weekly"}:
        # 周一作为一周起点
        monday = (now.date() - timedelta(days=now.weekday()))
        start = _to_local_naive(datetime(monday.year, monday.month, monday.day, 0, 0, 0))
        lookback_days = 45
        return start, _to_local_naive(end), lookback_days

    if w in {"month", "monthly"}:
        first = now.date().replace(day=1)
        start = _to_local_naive(datetime(first.year, first.month, first.day, 0, 0, 0))
        lookback_days = 120
        return start, _to_local_naive(end), lookback_days

    raise ValueError("window 参数不合法，应为 realtime/today/week/month/range")


def _to_doc(
    db: Session,
    rec: DataSourceContent,
    *,
    provider: str | None,
    use_llm: bool,
    is_list_parent: bool = False,
) -> _Doc | None:
    title = (rec.title or "").strip() or (rec.url or "") or str(rec.id)
    text = (rec.content or "").strip()
    if not text:
        return None

    # 内容时间抽取（不使用 fetched_at 作为事件时间）
    tr = extract_event_time_from_content(
        title=title,
        text=text,
        extra=rec.extra if isinstance(rec.extra, dict) else None,
        provider=provider,
        db=db,
        allow_llm=use_llm,
    )

    # 中文说明：兜底策略——若抽不到事件时间，但页面元信息里有发布时间/更新时间，则用它作为事件时间
    ev_start = tr.event_time_start
    ev_end = tr.event_time_end
    conf = float(tr.confidence or 0.0)
    if ev_end is None:
        extra = rec.extra if isinstance(rec.extra, dict) else {}
        anchor = _try_parse_iso_datetime(extra.get("modified_time")) or _try_parse_iso_datetime(extra.get("publish_time"))
        if anchor:
            ev_end = anchor
            ev_start = ev_start or anchor
            conf = max(conf, 0.40)

    # 中文说明：再兜底——相对时间（例如“23小时前”），用 fetched_at 回推
    if ev_end is None:
        rel = _try_parse_relative_time_delta(f"{title}\n{text}")
        if rel:
            base = _to_local_naive(rec.fetched_at) or rec.fetched_at
            ev_end = base - rel
            ev_start = ev_start or ev_end
            conf = max(conf, 0.42)

    # 中文说明：最后兜底——从 URL/标题/正文里解析日期（例如 issues/26-01-06-xxx 或 01-06 / 1月6日）
    if ev_end is None:
        base = _to_local_naive(rec.fetched_at) or rec.fetched_at
        dt = (
            _try_parse_date_from_mixed_text(text=rec.url or "", base=base)
            or _try_parse_date_from_mixed_text(text=title, base=base)
            or _try_parse_date_from_mixed_text(text=text, base=base)
        )
        if dt:
            ev_end = dt
            ev_start = ev_start or dt
            conf = max(conf, 0.40)

    ev_start = _to_local_naive(ev_start)
    ev_end = _to_local_naive(ev_end)

    prefix = re.sub(r"\s+", " ", text)[:160]
    mix = f"{title} {prefix}".strip()

    return _Doc(
        content_id=rec.id,
        datasource_id=rec.datasource_id,
        url=rec.url,
        title=title,
        text=text,
        fetched_at=rec.fetched_at,
        title_shingles=_shingles(mix, k=3),
        event_time_start=ev_start,
        event_time_end=ev_end,
        time_confidence=conf,
        is_list_parent=bool(is_list_parent),
    )


def build_window_hotspots(
    db: Session,
    *,
    window: str,
    now: datetime | None = None,
    limit: int = 20,
    sim_threshold: float = 0.42,
    provider: str | None = None,
    use_llm: bool = False,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """生成窗口热点（不落库，实时计算）。

    返回结构为 list[dict]，便于 API 直接响应。
    """

    now_dt = now or datetime.now()
    start, end, lookback_days = _window_range(
        window,
        now=now_dt,
        start_time=start_time,
        end_time=end_time,
    )
    wnorm = (window or "").strip().lower()

    # 候选集合：最近 N 天抓取记录（仅用于检索加速，不作为事件时间依据）
    fetch_start = now_dt - timedelta(days=lookback_days)
    rows = (
        db.query(DataSourceContent, DataSource)
        .join(DataSource, DataSource.id == DataSourceContent.datasource_id)
        .filter(DataSourceContent.source_type == "url")
        .filter(DataSourceContent.fetched_at >= fetch_start)
        .order_by(DataSourceContent.fetched_at.desc())
        .limit(5000)
        .all()
    )

    docs_raw: list[_Doc] = []

    # 中文说明：列表页策略
    # - 策略A：若数据源是列表页数据源，则默认只使用子页面记录（extra.is_discovered==True）
    # - 策略B：若列表页数据源在候选集中没有任何子页面记录，则父页面仅允许进入 week/month；realtime/today 禁止
    list_parent_candidates: list[tuple[DataSourceContent, DataSource]] = []
    list_ds_has_sub: dict[int, bool] = {}

    def _accept_doc(d: _Doc) -> bool:
        # 必须有 event_time_end 才能可靠进入窗口
        if not d.event_time_end:
            return False
        # 低置信度先不参与窗口榜（后续可做“低置信候选池”）
        if d.time_confidence < 0.35:
            return False
        if not (start <= d.event_time_end <= end):
            return False
        return True

    for rec, ds in rows:
        cfg = ds.config if isinstance(ds.config, dict) else {}
        if is_list_page_datasource(cfg):
            # 中文说明：优先用 is_discovered 标记；若缺失则用 URL 形态做一个轻量兜底
            if is_subpage_record(rec.extra) or _looks_like_detail_url(rec.url):
                list_ds_has_sub[ds.id] = True
                d = _to_doc(db, rec, provider=provider, use_llm=use_llm, is_list_parent=False)
                if d and _accept_doc(d):
                    docs_raw.append(d)
            else:
                list_ds_has_sub.setdefault(ds.id, False)
                list_parent_candidates.append((rec, ds))
            continue

        d = _to_doc(db, rec, provider=provider, use_llm=use_llm)
        if d and _accept_doc(d):
            docs_raw.append(d)

    # 策略B：仅 week/month 允许列表页父页面兜底进入
    allow_list_parent = wnorm in {"week", "weekly", "month", "monthly"}
    if allow_list_parent and list_parent_candidates:
        for rec, ds in list_parent_candidates:
            if list_ds_has_sub.get(ds.id) is True:
                continue
            d = _to_doc(db, rec, provider=provider, use_llm=use_llm, is_list_parent=True)
            if d and _accept_doc(d):
                docs_raw.append(d)

    # URL 去重
    docs = _dedupe_docs(docs_raw)
    if not docs:
        return []

    # 聚类：与簇内最大相似度比较
    clusters: list[list[_Doc]] = []
    for d in docs:
        placed = False
        for c in clusters:
            best_sim = 0.0
            for x in c:
                sim = _jaccard(d.title_shingles, x.title_shingles)
                if sim > best_sim:
                    best_sim = sim
            if best_sim >= sim_threshold:
                c.append(d)
                placed = True
                break
        if not placed:
            clusters.append([d])

    out: list[dict] = []
    for c in clusters:
        c_sorted = sorted(c, key=lambda x: (len(x.text), len(x.title)), reverse=True)
        leader = c_sorted[0]

        bullets_res = _pick_bullets(leader.text, top_k=5)
        bullets_texts = [t for t, sc in bullets_res]
        quotes_res = _pick_quotes(leader.text, top_k=3, exclude_texts=bullets_texts)

        bullets = bullets_res
        quotes = quotes_res
        summary = bullets[0][0] if bullets else None

        # 中文说明：混合簇计分规则
        # - 若簇内存在“非列表父页面来源”，则列表父页面来源不参与计分（避免聚合页抬高热度）
        # - 但列表父页面来源仍保留在 sources 中，用于溯源
        has_list_parent = any(bool(d.is_list_parent) for d in c_sorted)
        has_non_list_parent = any(not bool(d.is_list_parent) for d in c_sorted)
        scoring_docs = [d for d in c_sorted if not bool(d.is_list_parent)] if has_non_list_parent else c_sorted

        urls = [(d.url or "").strip().lower() for d in scoring_docs if (d.url or "").strip()]
        uniq_url_cnt = len(set(urls)) if urls else len(scoring_docs)
        domains = [_url_domain(d.url) for d in scoring_docs]
        uniq_domain_cnt = len({x for x in domains if x})

        # 聚合簇时间：取 end 最大值（更像“最新进展时间”）
        cluster_end = max([d.event_time_end for d in c_sorted if d.event_time_end] or [None])
        cluster_start = min([d.event_time_start for d in c_sorted if d.event_time_start] or [None])

        # 基础热度（复用日榜思路）
        quality = min(len(leader.text) / 1200.0, 1.2) + float(len(bullets)) * 0.15 + float(len(quotes)) * 0.10
        domain_penalty = 1.0
        if uniq_domain_cnt <= 1 and uniq_url_cnt >= 3:
            domain_penalty = 0.70
        elif uniq_domain_cnt == 2 and uniq_url_cnt >= 5:
            domain_penalty = 0.85
        base_hot = (float(uniq_url_cnt) * 1.2 + float(uniq_domain_cnt) * 0.9 + quality) * domain_penalty

        # 新鲜度因子：越接近 now 越高（基于事件时间，不基于抓取时间）
        recency = 1.0
        if cluster_end:
            hours = max(0.0, (now_dt - cluster_end).total_seconds() / 3600.0)
            recency = math.exp(-hours / 18.0)

        final_hot = base_hot * (0.6 + 0.4 * recency)

        extreme_max_len = 8000
        out.append(
            {
                "window": window,
                "title": leader.title[:255],
                "summary": summary,
                "hot_score": float(final_hot),
                "event_time_start": cluster_start.isoformat() if cluster_start else None,
                "event_time_end": cluster_end.isoformat() if cluster_end else None,
                "source_count": int(len(c_sorted)),
                "uniq_url_cnt": int(uniq_url_cnt),
                "uniq_domain_cnt": int(uniq_domain_cnt),
                "domain_penalty": float(domain_penalty),
                "recency": float(recency),
                "flags": {
                    "list_parent_fallback": bool(leader.is_list_parent),
                    "has_list_parent": bool(has_list_parent),
                },
                "extra": {
                    "cluster_size": len(c_sorted),
                    # 中文说明：列表页父页面（聚合页）进入窗口热点时打标，便于前端/后续策略识别
                    "is_list_parent": bool(leader.is_list_parent),
                    "has_list_parent": bool(has_list_parent),
                },
                "bullets": [
                    {
                        "type": "bullet",
                        "text": _truncate_text(t, max_len=extreme_max_len),
                        "score": float(sc),
                        "source_url": leader.url,
                        "source_content_id": leader.content_id,
                        "position": i,
                    }
                    for i, (t, sc) in enumerate(bullets)
                ],
                "quotes": [
                    {
                        "type": "quote",
                        "text": _truncate_text(t, max_len=extreme_max_len),
                        "score": float(sc),
                        "source_url": leader.url,
                        "source_content_id": leader.content_id,
                        "position": i,
                    }
                    for i, (t, sc) in enumerate(quotes)
                ],
                "sources": [
                    {
                        "content_id": d.content_id,
                        "url": d.url,
                        "title": d.title[:255] if d.title else None,
                        "domain": _url_domain(d.url),
                        "is_list_parent": bool(d.is_list_parent),
                        "time_confidence": float(d.time_confidence),
                        "event_time_end": d.event_time_end.isoformat() if d.event_time_end else None,
                    }
                    for d in c_sorted[:50]
                ],
            }
        )

    out.sort(key=lambda x: x.get("hot_score") or 0.0, reverse=True)
    return out[: max(1, min(200, int(limit)))]
