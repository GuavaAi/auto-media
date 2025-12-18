from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.datasource_content import DataSourceContent
from app.models.event_cluster import EventCluster, EventClusterItem, EventClusterSource


@dataclass
class _Doc:
    content_id: int
    url: Optional[str]
    title: str
    text: str
    fetched_at: datetime

    title_shingles: set[str]


def _normalize_text(s: str) -> str:
    s = s or ""
    s = s.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _shingles(s: str, k: int = 2) -> set[str]:
    # 中文分词先不引入第三方依赖，使用字符 n-gram 作为相似度基础
    s = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", _normalize_text(s))
    if len(s) < k:
        return {s} if s else set()
    return {s[i : i + k] for i in range(0, len(s) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    union = len(a | b)
    return inter / union if union else 0.0


def _split_paragraphs(text: str) -> List[str]:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in re.split(r"\n{2,}", t) if p and p.strip()]
    if parts:
        return parts
    # 兜底按单行切
    return [p.strip() for p in t.split("\n") if p.strip()]


def _sentence_candidates(paragraph: str) -> List[str]:
    # 资讯类要点更像“短句”，这里做最轻量的句子切分
    p = paragraph.replace("\r\n", "\n").replace("\r", "\n")
    p = re.sub(r"\s+", " ", p).strip()
    if not p:
        return []
    segs = re.split(r"[。！？!?；;]\s*", p)
    return [s.strip() for s in segs if s and len(s.strip()) >= 10]


def _score_text(s: str) -> float:
    # 规则打分：长度、数字密度、信息密度（非常粗）
    s = s or ""
    base = min(len(s) / 80.0, 2.0)
    num_bonus = 0.6 if re.search(r"\d", s) else 0.0
    return base + num_bonus


def _truncate_text(s: str, max_len: int) -> str:
    """截断超长文本（仅防御极端情况）。

    中文说明：之前对要点/引用做了较小阈值（300/800）的截断，会导致 UI 出现大量“...”。
    现改为策略B：只对极端超长的异常文本做硬上限截断，避免数据库/前端承载过大。
    """
    s = s or ""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."


def _pick_bullets(text: str, top_k: int = 5) -> List[Tuple[str, float]]:
    bullets: List[Tuple[str, float]] = []
    for para in _split_paragraphs(text):
        for sent in _sentence_candidates(para):
            score = _score_text(sent)
            bullets.append((sent, score))
    bullets.sort(key=lambda x: x[1], reverse=True)

    seen: set[str] = set()
    out: List[Tuple[str, float]] = []
    for s, sc in bullets:
        key = _normalize_text(s)
        if key in seen:
            continue
        seen.add(key)
        out.append((s, sc))
        if len(out) >= top_k:
            break
    return out


def _pick_quotes(text: str, top_k: int = 3) -> List[Tuple[str, float]]:
    # 引用更偏“可直接摘录的句子”，优先句子级（避免整篇长段落写入）
    cands: List[Tuple[str, float]] = []
    for para in _split_paragraphs(text):
        for sent in _sentence_candidates(para):
            cands.append((sent, _score_text(sent) + 0.2))
    cands.sort(key=lambda x: x[1], reverse=True)
    return cands[:top_k]


def _fetch_day_contents(db: Session, day: date) -> List[DataSourceContent]:
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    return (
        db.query(DataSourceContent)
        .filter(DataSourceContent.source_type == "url")
        .filter(DataSourceContent.fetched_at >= start, DataSourceContent.fetched_at < end)
        .order_by(DataSourceContent.fetched_at.desc())
        .all()
    )


def _to_doc(rec: DataSourceContent) -> _Doc:
    title = (rec.title or "").strip() or (rec.url or "") or str(rec.id)
    text = rec.content or ""
    return _Doc(
        content_id=rec.id,
        url=rec.url,
        title=title,
        text=text,
        fetched_at=rec.fetched_at,
        title_shingles=_shingles(title, k=2),
    )


def build_daily_hotspots(
    db: Session,
    day: date,
    limit: int = 20,
    sim_threshold: float = 0.42,
) -> List[EventCluster]:
    """生成某日热点榜单（事件簇），幂等：会覆盖该日已有结果。"""

    # 1) 取当天抓取记录（空态时不覆盖旧榜单，避免误删）
    contents = _fetch_day_contents(db, day)
    docs = [_to_doc(r) for r in contents if (r.content or "").strip()]
    if not docs:
        raise ValueError("当日无可用采集数据：请先完成采集（data_source_contents）或选择有数据的日期")

    # 2) 清理旧数据（幂等，仅在有新数据时执行）
    old_events = db.query(EventCluster).filter(EventCluster.day == day).all()
    if old_events:
        old_ids = [e.id for e in old_events]
        db.query(EventClusterItem).filter(EventClusterItem.event_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(EventClusterSource).filter(EventClusterSource.event_id.in_(old_ids)).delete(synchronize_session=False)
        db.query(EventCluster).filter(EventCluster.id.in_(old_ids)).delete(synchronize_session=False)
        db.flush()

    # 3) 简单聚类：按标题 n-gram jaccard
    clusters: List[List[_Doc]] = []
    for d in docs:
        placed = False
        for c in clusters:
            rep = c[0]
            if _jaccard(d.title_shingles, rep.title_shingles) >= sim_threshold:
                c.append(d)
                placed = True
                break
        if not placed:
            clusters.append([d])

    # 4) 对每个簇生成事件卡片
    events: List[EventCluster] = []
    for c in clusters:
        # 选主文：标题更长/文本更长优先（粗略）
        c_sorted = sorted(c, key=lambda x: (len(x.text), len(x.title)), reverse=True)
        leader = c_sorted[0]

        bullets = _pick_bullets(leader.text, top_k=5)
        quotes = _pick_quotes(leader.text, top_k=3)

        summary = bullets[0][0] if bullets else None

        hot_score = float(len(c)) * 1.5 + float(len(bullets)) * 0.3 + float(len(quotes)) * 0.2

        evt = EventCluster(
            day=day,
            title=leader.title[:255],
            summary=summary,
            hot_score=hot_score,
            keywords=None,
            extra={"cluster_size": len(c)},
        )
        db.add(evt)
        db.flush()

        # 来源
        for d in c_sorted:
            db.add(
                EventClusterSource(
                    event_id=evt.id,
                    content_id=d.content_id,
                    url=d.url,
                    title=d.title[:255] if d.title else None,
                    weight=1.0,
                )
            )

        # 要点
        # 中文说明：策略B——仅对“极端超长”文本做硬上限截断，避免 UI 频繁出现“...”。
        extreme_max_len = 8000
        for i, (t, sc) in enumerate(bullets):
            db.add(
                EventClusterItem(
                    event_id=evt.id,
                    type="bullet",
                    text=_truncate_text(t, max_len=extreme_max_len),
                    source_url=leader.url,
                    source_content_id=leader.content_id,
                    position=i,
                    score=float(sc),
                )
            )

        # 引用
        for i, (t, sc) in enumerate(quotes):
            db.add(
                EventClusterItem(
                    event_id=evt.id,
                    type="quote",
                    text=_truncate_text(t, max_len=extreme_max_len),
                    source_url=leader.url,
                    source_content_id=leader.content_id,
                    position=i,
                    score=float(sc),
                )
            )

        events.append(evt)

    # 5) 排序取 TopN
    events.sort(key=lambda e: (e.hot_score or 0.0), reverse=True)
    events = events[: max(1, min(200, limit))]

    # 只保留 TopN，清理多余事件
    keep_ids = {e.id for e in events}
    all_ids = [e.id for e in db.query(EventCluster).filter(EventCluster.day == day).all()]
    drop_ids = [eid for eid in all_ids if eid not in keep_ids]
    if drop_ids:
        db.query(EventClusterItem).filter(EventClusterItem.event_id.in_(drop_ids)).delete(synchronize_session=False)
        db.query(EventClusterSource).filter(EventClusterSource.event_id.in_(drop_ids)).delete(synchronize_session=False)
        db.query(EventCluster).filter(EventCluster.id.in_(drop_ids)).delete(synchronize_session=False)

    db.flush()
    return events
