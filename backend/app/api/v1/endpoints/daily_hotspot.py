from __future__ import annotations

from datetime import date
import json
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app import deps
from app.models.event_cluster import EventCluster, EventClusterItem, EventClusterSource
from app.schemas.daily_hotspot import (
    DailyHotspotDetailResponse,
    DailyHotspotEventOut,
    DailyHotspotItemOut,
    DailyHotspotListResponse,
    DailyHotspotListSmartFilterRequest,
    DailyHotspotListSmartFilterResponse,
    DailyHotspotSmartFilterRequest,
    DailyHotspotSmartFilterResponse,
    DailyHotspotSourceOut,
)
from app.services.daily_hotspot_builder import build_daily_hotspots
from app.services.llm_provider import get_provider

router = APIRouter()


def _extract_first_json_obj(text: str) -> Optional[dict]:
    """从模型输出中提取第一个 JSON 对象。

    中文说明：模型有时会输出 ```json ...``` 或夹杂说明文字，这里做一个鲁棒解析。
    """

    s = (text or "").strip()
    if not s:
        return None

    # 1) 优先尝试整体就是 JSON
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    # 2) 尝试提取 ```json ...``` 代码块
    m = re.search(r"```json\s*(\{[\s\S]*?\})\s*```", s, flags=re.IGNORECASE)
    if m:
        try:
            obj = json.loads(m.group(1))
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass

    # 3) 兜底：提取第一个大括号块（可能包含嵌套）
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


def _build_smart_filter_prompt(
    *,
    title: str,
    summary: str | None,
    instruction: str | None,
    items: list[dict],
) -> str:
    # 中文说明：要求模型仅输出 JSON，便于后端解析
    inst = (instruction or "").strip()
    summary_str = (summary or "").strip()
    lines: list[str] = []
    lines.append("你是一个内容编辑助手。你的任务是从候选条目中挑选‘与热点事件高度相关、可用于写软文/公众号文章的素材’。")
    lines.append("请严格按 JSON 格式输出，不要输出任何多余文字。")
    if inst:
        lines.append(f"【额外筛选指令】{inst}")
    lines.append(f"【事件标题】{(title or '').strip()}")
    if summary_str:
        lines.append(f"【事件摘要】{summary_str}")
    lines.append("\n【候选条目】")
    for it in items:
        tid = it.get("id")
        ttype = it.get("type")
        text = (it.get("text") or "").strip()
        # 控制 prompt 体积，每条最多 400 字
        if len(text) > 400:
            text = text[:400] + "..."
        lines.append(f"- id={tid} type={ttype} text={text}")

    lines.append(
        "\n【输出 JSON 规范】\n"
        "{\n"
        "  \"selected\": [\n"
        "    {\"id\": 123, \"score\": 0.0, \"reason\": \"...\"}\n"
        "  ]\n"
        "}\n"
        "要求：\n"
        "- score 范围 0~1，越大越相关\n"
        "- 只返回你推荐的条目 id（selected）\n"
    )
    return "\n".join(lines).strip() + "\n"


def _build_list_smart_filter_prompt(
    *,
    day: date,
    topic: str,
    instruction: str | None,
    events: list[dict],
) -> str:
    # 中文说明：榜单智能筛选——从热点事件列表中挑选与 topic 最相关的事件
    t = (topic or "").strip()
    inst = (instruction or "").strip()

    lines: list[str] = []
    lines.append("你是一个内容选题助手。你需要根据用户主题，从当天热点事件列表中挑选最相关的事件。")
    lines.append("请严格按 JSON 格式输出，不要输出任何多余文字。")
    lines.append(f"【日期】{day.isoformat()}")
    lines.append(f"【用户主题】{t}")
    if inst:
        lines.append(f"【额外筛选指令】{inst}")

    lines.append("\n【候选热点事件】")
    for e in events:
        eid = e.get("id")
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or "").strip()
        hot = e.get("hot_score")
        sc = e.get("source_count")
        # 控制 prompt 体积
        if len(summary) > 160:
            summary = summary[:160] + "..."
        lines.append(f"- id={eid} hot_score={hot} source_count={sc} title={title} summary={summary}")

    lines.append(
        "\n【输出 JSON 规范】\n"
        "{\n"
        "  \"selected\": [\n"
        "    {\"id\": 123, \"score\": 0.0, \"reason\": \"...\"}\n"
        "  ]\n"
        "}\n"
        "要求：\n"
        "- score 范围 0~1，越大越相关\n"
        "- 只返回你推荐的热点事件 id（selected）\n"
    )
    return "\n".join(lines).strip() + "\n"


@router.post("/build", response_model=DailyHotspotListResponse, summary="手动生成某日热点榜单")
def build_daily_hotspots_endpoint(
    day: date = Query(..., description="日期 YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=200, description="榜单条数"),
    db: Session = Depends(deps.get_db),
) -> DailyHotspotListResponse:
    try:
        events = build_daily_hotspots(db, day=day, limit=limit)
        db.commit()
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

    items: List[DailyHotspotEventOut] = []
    for e in events:
        source_count = (
            db.query(EventClusterSource)
            .filter(EventClusterSource.event_id == e.id)
            .count()
        )
        items.append(
            DailyHotspotEventOut(
                id=e.id,
                day=e.day,
                title=e.title,
                summary=e.summary,
                hot_score=float(e.hot_score or 0.0),
                keywords=e.keywords,
                source_count=source_count,
                created_at=e.created_at,
            )
        )

    return DailyHotspotListResponse(day=day, items=items)


@router.post(
    "/smart-filter",
    response_model=DailyHotspotListSmartFilterResponse,
    summary="热点榜单智能筛选：按主题筛选相关热点事件",
)
def smart_filter_daily_hotspot_list(
    payload: DailyHotspotListSmartFilterRequest,
    db: Session = Depends(deps.get_db),
) -> DailyHotspotListSmartFilterResponse:
    topic = (payload.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic 不能为空")

    rows = (
        db.query(EventCluster)
        .filter(EventCluster.day == payload.day)
        .order_by(desc(EventCluster.hot_score), desc(EventCluster.id))
        .limit(int(payload.limit or 50))
        .all()
    )
    if not rows:
        return DailyHotspotListSmartFilterResponse(
            day=payload.day,
            topic=topic,
            recommended_event_ids=[],
            decisions=[],
        )

    events = []
    for e in rows:
        source_count = (
            db.query(EventClusterSource)
            .filter(EventClusterSource.event_id == e.id)
            .count()
        )
        events.append(
            {
                "id": e.id,
                "title": e.title,
                "summary": e.summary,
                "hot_score": float(e.hot_score or 0.0),
                "source_count": int(source_count),
            }
        )

    prompt = _build_list_smart_filter_prompt(
        day=payload.day,
        topic=topic,
        instruction=payload.instruction,
        events=events,
    )

    try:
        provider = get_provider(payload.provider, db=db)
        raw = provider.generate(prompt, temperature=float(payload.temperature or 0.2), length=1200)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"智能筛选失败：{exc}") from exc

    obj = _extract_first_json_obj(raw)
    if not obj or not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail=f"智能筛选返回无法解析：{raw[:500]}")

    selected = obj.get("selected")
    selected_map: dict[int, dict] = {}
    if isinstance(selected, list):
        for x in selected:
            if not isinstance(x, dict):
                continue
            try:
                xid = int(x.get("id"))
            except Exception:
                continue
            selected_map[xid] = x

    recommended_ids: list[int] = []
    decisions = []
    for e in events:
        eid = int(e["id"])
        meta = selected_map.get(eid)
        rec = meta is not None
        score = 0.0
        reason = None
        if isinstance(meta, dict):
            try:
                score = float(meta.get("score") or 0.0)
            except Exception:
                score = 0.0
            r = meta.get("reason")
            reason = r.strip() if isinstance(r, str) and r.strip() else None
        if rec:
            recommended_ids.append(eid)
        decisions.append(
            {
                "event_id": eid,
                "recommended": rec,
                "score": score,
                "reason": reason,
            }
        )

    return DailyHotspotListSmartFilterResponse(
        day=payload.day,
        topic=topic,
        recommended_event_ids=recommended_ids,
        decisions=decisions,
    )


@router.get("/", response_model=DailyHotspotListResponse, summary="获取某日热点榜单（Top20）")
def list_daily_hotspots(
    day: date = Query(..., description="日期 YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=200, description="榜单条数"),
    db: Session = Depends(deps.get_db),
) -> DailyHotspotListResponse:
    rows = (
        db.query(EventCluster)
        .filter(EventCluster.day == day)
        .order_by(desc(EventCluster.hot_score), desc(EventCluster.id))
        .limit(limit)
        .all()
    )

    items: List[DailyHotspotEventOut] = []
    for e in rows:
        source_count = (
            db.query(EventClusterSource)
            .filter(EventClusterSource.event_id == e.id)
            .count()
        )
        items.append(
            DailyHotspotEventOut(
                id=e.id,
                day=e.day,
                title=e.title,
                summary=e.summary,
                hot_score=float(e.hot_score or 0.0),
                keywords=e.keywords,
                source_count=source_count,
                created_at=e.created_at,
            )
        )

    return DailyHotspotListResponse(day=day, items=items)


@router.get("/{event_id}", response_model=DailyHotspotDetailResponse, summary="热点事件详情（要点+引用+来源）")
def get_daily_hotspot_detail(event_id: int, db: Session = Depends(deps.get_db)) -> DailyHotspotDetailResponse:
    event = db.query(EventCluster).filter(EventCluster.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="热点事件不存在")

    sources = (
        db.query(EventClusterSource)
        .filter(EventClusterSource.event_id == event_id)
        .order_by(desc(EventClusterSource.weight), desc(EventClusterSource.id))
        .all()
    )

    items = (
        db.query(EventClusterItem)
        .filter(EventClusterItem.event_id == event_id)
        .order_by(EventClusterItem.type.asc(), EventClusterItem.position.asc(), desc(EventClusterItem.score))
        .all()
    )

    bullets: List[DailyHotspotItemOut] = []
    quotes: List[DailyHotspotItemOut] = []
    facts: List[DailyHotspotItemOut] = []
    for it in items:
        out = DailyHotspotItemOut(
            id=it.id,
            type=it.type,
            text=it.text,
            source_url=it.source_url,
            source_content_id=it.source_content_id,
            position=it.position,
            score=float(it.score or 0.0),
            extra=it.extra,
        )
        if it.type == "bullet":
            bullets.append(out)
        elif it.type == "quote":
            quotes.append(out)
        else:
            facts.append(out)

    source_out = [
        DailyHotspotSourceOut(
            id=s.id,
            content_id=s.content_id,
            url=s.url,
            title=s.title,
            weight=float(s.weight or 0.0),
        )
        for s in sources
    ]

    evt_out = DailyHotspotEventOut(
        id=event.id,
        day=event.day,
        title=event.title,
        summary=event.summary,
        hot_score=float(event.hot_score or 0.0),
        keywords=event.keywords,
        source_count=len(source_out),
        created_at=event.created_at,
    )

    return DailyHotspotDetailResponse(
        event=evt_out,
        bullets=bullets,
        quotes=quotes,
        facts=facts,
        sources=source_out,
    )


@router.post(
    "/{event_id}/smart-filter",
    response_model=DailyHotspotSmartFilterResponse,
    summary="热点智能筛选：模型判断相关性，返回推荐条目",
)
def smart_filter_daily_hotspot(
    event_id: int,
    payload: DailyHotspotSmartFilterRequest,
    db: Session = Depends(deps.get_db),
) -> DailyHotspotSmartFilterResponse:
    event = db.query(EventCluster).filter(EventCluster.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="热点事件不存在")

    include_types = payload.include_types
    allow = None
    if isinstance(include_types, list) and include_types:
        allow = {str(x).strip().lower() for x in include_types if str(x).strip()}

    q = db.query(EventClusterItem).filter(EventClusterItem.event_id == event_id)
    if allow:
        q = q.filter(EventClusterItem.type.in_(list(allow)))

    rows = (
        q.order_by(EventClusterItem.type.asc(), EventClusterItem.position.asc(), desc(EventClusterItem.score))
        .limit(int(payload.max_items or 30))
        .all()
    )
    if not rows:
        return DailyHotspotSmartFilterResponse(event_id=event_id, recommended_item_ids=[], decisions=[])

    items = [
        {
            "id": it.id,
            "type": (it.type or "").strip().lower(),
            "text": it.text,
        }
        for it in rows
    ]

    prompt = _build_smart_filter_prompt(
        title=event.title,
        summary=event.summary,
        instruction=payload.instruction,
        items=items,
    )

    try:
        provider = get_provider(payload.provider, db=db)
        raw = provider.generate(prompt, temperature=float(payload.temperature or 0.2), length=1200)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"智能筛选失败：{exc}") from exc

    obj = _extract_first_json_obj(raw)
    if not obj or not isinstance(obj, dict):
        raise HTTPException(status_code=400, detail=f"智能筛选返回无法解析：{raw[:500]}")

    selected = obj.get("selected")
    selected_map: dict[int, dict] = {}
    if isinstance(selected, list):
        for x in selected:
            if not isinstance(x, dict):
                continue
            try:
                xid = int(x.get("id"))
            except Exception:
                continue
            selected_map[xid] = x

    recommended_ids: list[int] = []
    decisions = []
    for it in items:
        iid = int(it["id"])
        meta = selected_map.get(iid)
        rec = meta is not None
        score = 0.0
        reason = None
        if isinstance(meta, dict):
            try:
                score = float(meta.get("score") or 0.0)
            except Exception:
                score = 0.0
            r = meta.get("reason")
            reason = r.strip() if isinstance(r, str) and r.strip() else None
        if rec:
            recommended_ids.append(iid)
        decisions.append(
            {
                "id": iid,
                "type": it.get("type"),
                "recommended": rec,
                "score": score,
                "reason": reason,
            }
        )

    return DailyHotspotSmartFilterResponse(
        event_id=event_id,
        recommended_item_ids=recommended_ids,
        decisions=decisions,
    )
