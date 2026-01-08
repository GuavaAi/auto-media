from __future__ import annotations

import re
from urllib.parse import urlparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent
from app.models.event_cluster import EventCluster, EventClusterItem, EventClusterSource
from app.services.datasource_config_utils import is_list_page_datasource, is_subpage_record


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


def _url_domain(url: Optional[str]) -> Optional[str]:
    u = (url or "").strip()
    if not u:
        return None
    try:
        host = (urlparse(u).netloc or "").strip().lower()
    except Exception:
        return None
    if not host:
        return None
    if host.startswith("www."):
        host = host[4:]
    return host or None


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


def _is_noise_sentence(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return True
    # 过长/过短的句子不适合作“要点/引用”
    if len(t) < 10:
        return True
    if len(t) > 180:
        return True
    low = _normalize_text(t)
    # 中文说明：过滤常见广告/引流/模板句，避免污染要点
    noise_phrases = [
        "点击",
        "扫码",
        "关注",
        "公众号",
        "原文",
        "转载",
        "免责声明",
        "版权",
        "更多精彩",
        "长按",
        "点赞",
        "在看",
        "转发",
        "私信",
        "加微信",
        "客服",
        "二维码",
        "文章来源",
        "想了解",
        "请点击",
        "其它版块",
        "平台官方",
    ]
    if any(p in low for p in noise_phrases):
        return True
    return False


def _score_text(s: str) -> float:
    s = s or ""
    base = min(len(s) / 80.0, 2.0)

    num_bonus = 0.8 if re.search(r"\d", s) else 0.0

    org_bonus = 0.0
    if re.search(r"(公司|集团|大学|学院|研究院|研究中心|实验室|委员会|协会|研究员|教授|CEO|CTO|OpenAI|Google|微软|英伟达|亚马逊)", s, re.IGNORECASE):
        org_bonus = 0.45

    action_bonus = 0.0
    if re.search(r"(发布|推出|宣布|上线|完成|融资|募资|开源|杀青|启动|预览|预告|进入|提升|整治|扩建|量产)", s):
        action_bonus = 0.35

    question_penalty = 0.0
    if "？" in s or "?" in s:
        question_penalty = -0.35

    slogan_penalty = 0.0
    if re.search(r"(让我们一起期待|不久之后|意义非凡|可不简单|谁能想到|是不是更)", s):
        slogan_penalty = -0.25

    return base + num_bonus + org_bonus + action_bonus + question_penalty + slogan_penalty


def _is_nav_line(line: str) -> bool:
    low = _normalize_text(line)
    if not low:
        return True
    if low in {"ai top100", "aitop100", "ai top 100", "ai top100平台"}:
        return True
    if re.fullmatch(r"\d{1,3}\s*(小时|分钟|天)\s*前", low):
        return True
    if low in {"|", "-"}:
        return True
    if any(x in low for x in ["平台官方交流社群", "二维码", "文章来源", "想了解", "请点击", "超链接", "其它版块", "ai资讯专区", "ai工具集", "ai小说", "创作大赛", "ai活动"]):
        return True
    return False


def _is_heading_line(line: str) -> bool:
    t = (line or "").strip()
    if not t:
        return False
    if len(t) < 8 or len(t) > 30:
        return False
    if re.search(r"[。！？!?；;，,：:]", t):
        return False
    if re.search(r"\d", t):
        return False
    return True


def _clean_scraped_text(text: str) -> str:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = [x.strip() for x in t.split("\n")]
    lines = [x for x in raw_lines if x and not _is_nav_line(x)]
    if not lines:
        return (text or "").strip()

    paragraphs: list[str] = []
    cur = ""
    for ln in lines:
        if _is_heading_line(ln):
            if cur.strip():
                paragraphs.append(cur.strip())
            cur = ln.strip()
            continue

        if not cur:
            cur = ln
            continue

        prev = cur.rstrip()
        # 抓取常见错误：把一个长句硬断成多行（如“职业视角结合”\n“人工智能”\n“直播”）
        should_merge_tight = (
            (not re.search(r"[。！？!?；;]$", prev) and len(ln) <= 20)
            or prev.endswith(("结合", "通过", "以及", "与", "和", "、", "的"))
            or len(ln) <= 8
        )
        if should_merge_tight:
            cur = prev + ln
        else:
            cur = prev + " " + ln

    if cur.strip():
        paragraphs.append(cur.strip())

    return "\n\n".join(paragraphs)


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
    text = _clean_scraped_text(text)
    bullets: List[Tuple[str, float, int]] = []
    paras = _split_paragraphs(text)
    for pi, para in enumerate(paras):
        for sent in _sentence_candidates(para):
            if _is_noise_sentence(sent):
                continue
            score = _score_text(sent)
            bullets.append((sent, score, pi))
    bullets.sort(key=lambda x: x[1], reverse=True)

    seen_keys: List[set[str]] = []
    out: List[Tuple[str, float]] = []
    per_para_count: dict[int, int] = {}
    for s, sc, pi in bullets:
        # 中文说明：段落多样性控制，避免 TopK 全来自同一段
        if per_para_count.get(pi, 0) >= 2:
            continue
        sh = _shingles(s, k=2)
        if any(_jaccard(sh, old) >= 0.82 for old in seen_keys):
            continue
        seen_keys.append(sh)
        per_para_count[pi] = per_para_count.get(pi, 0) + 1
        out.append((s, sc))
        if len(out) >= top_k:
            break
    return out


def _pick_quotes(text: str, top_k: int = 3, exclude_texts: List[str] = None) -> List[Tuple[str, float]]:
    # 引用更偏“可直接摘录的句子”，优先句子级（避免整篇长段落写入）
    text = _clean_scraped_text(text)
    cands: List[Tuple[str, float]] = []
    excludes = {(_normalize_text(t)) for t in (exclude_texts or [])}

    for para in _split_paragraphs(text):
        for sent in _sentence_candidates(para):
            if _is_noise_sentence(sent):
                continue
            # 中文说明：排除已选为要点的句子（或相似度极高的句子）
            if _normalize_text(sent) in excludes:
                continue
            cands.append((sent, _score_text(sent) + 0.2))
    cands.sort(key=lambda x: x[1], reverse=True)
    out: List[Tuple[str, float]] = []
    seen_keys: List[set[str]] = []
    for s, sc in cands:
        sh = _shingles(s, k=2)
        if any(_jaccard(sh, old) >= 0.82 for old in seen_keys):
            continue
        seen_keys.append(sh)
        out.append((s, sc))
        if len(out) >= top_k:
            break
    return out


def _dedupe_docs(docs: Sequence[_Doc]) -> List[_Doc]:
    """按 URL 去重当天抓取记录。

    中文说明：同一 URL 可能被重复抓取（或参数差异但实为同文），会把热度“刷大”。
    这里优先用 url 作为 key；同 key 下保留文本更长的那条（更像正文页）。
    """

    best: dict[str, _Doc] = {}
    out: List[_Doc] = []
    for d in docs:
        key = (d.url or "").strip().lower()
        if not key:
            out.append(d)
            continue
        old = best.get(key)
        if old is None or (len(d.text) > len(old.text)):
            best[key] = d
    if best:
        out.extend(best.values())
    out.sort(key=lambda x: x.fetched_at, reverse=True)
    return out


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
    prefix = re.sub(r"\s+", " ", (text or "").strip())[:160]
    mix = f"{title} {prefix}".strip()
    return _Doc(
        content_id=rec.id,
        url=rec.url,
        title=title,
        text=text,
        fetched_at=rec.fetched_at,
        # 中文说明：标题+正文前缀的 n-gram，有助于减少“标题套话”导致的误聚类
        title_shingles=_shingles(mix, k=3),
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

    # 中文说明：列表页（聚合页）父页面可能包含多条资讯，容易污染热点。
    # 策略A：若数据源配置表明会抓子页面（列表页数据源），则默认过滤父页面，只保留子页面记录参与日榜。
    ds_ids = sorted({c.datasource_id for c in contents})
    ds_cfg_map: dict[int, dict] = {}
    if ds_ids:
        for ds_id, cfg in db.query(DataSource.id, DataSource.config).filter(DataSource.id.in_(ds_ids)).all():
            ds_cfg_map[int(ds_id)] = cfg if isinstance(cfg, dict) else {}

    filtered: list[DataSourceContent] = []
    for r in contents:
        cfg = ds_cfg_map.get(r.datasource_id) or {}
        if is_list_page_datasource(cfg) and not is_subpage_record(r.extra):
            continue
        filtered.append(r)

    contents = filtered
    docs = [_to_doc(r) for r in contents if (r.content or "").strip()]
    docs = _dedupe_docs(docs)
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
            # 中文说明：使用“与簇内最大相似度”而非单代表，降低顺序敏感性
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

    # 4) 对每个簇生成事件卡片
    events: List[EventCluster] = []
    for c in clusters:
        # 选主文：标题更长/文本更长优先（粗略）
        c_sorted = sorted(c, key=lambda x: (len(x.text), len(x.title)), reverse=True)
        leader = c_sorted[0]

        bullets_res = _pick_bullets(leader.text, top_k=5)
        bullets_texts = [t for t, sc in bullets_res]
        quotes_res = _pick_quotes(leader.text, top_k=3, exclude_texts=bullets_texts)

        bullets = bullets_res
        quotes = quotes_res

        summary = bullets[0][0] if bullets else None

        # 热度评分（B）：更偏“真实热度”——来源数 + 域名多样性（防单站刷屏） + 轻量内容质量
        urls = [(d.url or "").strip().lower() for d in c_sorted if (d.url or "").strip()]
        uniq_url_cnt = len(set(urls)) if urls else len(c_sorted)
        domains = [_url_domain(d.url) for d in c_sorted]
        uniq_domain_cnt = len({x for x in domains if x})

        # 内容质量：bullet/quote 的有效数量（经过过滤与去重后） + leader 文本长度上限
        quality = min(len(leader.text) / 1200.0, 1.2) + float(len(bullets)) * 0.15 + float(len(quotes)) * 0.10

        # 单域名惩罚：域名越集中，惩罚越大（避免单站大量转载顶榜）
        domain_penalty = 1.0
        if uniq_domain_cnt <= 1 and uniq_url_cnt >= 3:
            domain_penalty = 0.70
        elif uniq_domain_cnt == 2 and uniq_url_cnt >= 5:
            domain_penalty = 0.85

        hot_score = (float(uniq_url_cnt) * 1.2 + float(uniq_domain_cnt) * 0.9 + quality) * domain_penalty

        evt = EventCluster(
            day=day,
            title=leader.title[:255],
            summary=summary,
            hot_score=hot_score,
            keywords=None,
            extra={
                "cluster_size": len(c),
                "uniq_url_cnt": int(uniq_url_cnt),
                "uniq_domain_cnt": int(uniq_domain_cnt),
                "domain_penalty": float(domain_penalty),
                "quality": float(quality),
            },
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
