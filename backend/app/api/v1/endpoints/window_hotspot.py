from __future__ import annotations

from datetime import datetime
import json
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import deps
from app.schemas.window_hotspot import (
    WindowHotspotBuildRequest,
    WindowHotspotListResponse,
    WindowHotspotListSmartFilterRequest,
    WindowHotspotListSmartFilterResponse,
)
from app.services.window_hotspot_builder import build_window_hotspots
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


def _build_window_list_smart_filter_prompt(*, window: str, topic: str, instruction: str | None, events: list[dict]) -> str:
    # 中文说明：榜单智能筛选——从窗口热点事件列表中挑选与 topic 最相关的事件
    t = (topic or "").strip()
    inst = (instruction or "").strip()

    lines: list[str] = []
    lines.append("你是一个内容选题助手。你需要根据用户主题，从窗口热点事件列表中挑选最相关的事件。")
    lines.append("请严格按 JSON 格式输出，不要输出任何多余文字。")
    lines.append(f"【窗口】{(window or '').strip()}")
    lines.append(f"【用户主题】{t}")
    if inst:
        lines.append(f"【额外筛选指令】{inst}")

    lines.append("\n【候选热点事件】")
    for e in events:
        idx = e.get("id")
        title = (e.get("title") or "").strip()
        summary = (e.get("summary") or "").strip()
        hot = e.get("hot_score")
        sc = e.get("source_count")
        # 控制 prompt 体积
        if len(summary) > 160:
            summary = summary[:160] + "..."
        lines.append(f"- id={idx} hot_score={hot} source_count={sc} title={title} summary={summary}")

    lines.append(
        "\n【输出 JSON 规范】\n"
        "{\n"
        '  "selected": [\n'
        '    {"id": 123, "score": 0.0, "reason": "..."}\n'
        "  ]\n"
        "}\n"
        "要求：\n"
        "- score 范围 0~1，越大越相关\n"
        "- 只返回你推荐的热点事件 id（selected）\n"
    )
    return "\n".join(lines).strip() + "\n"


@router.post("/build", response_model=WindowHotspotListResponse, summary="生成窗口热点榜单（实时/今日/本周/本月，基于内容时间）")
def build_window_hotspot_endpoint(
    payload: WindowHotspotBuildRequest,
    db: Session = Depends(deps.get_db),
) -> WindowHotspotListResponse:
    try:
        items = build_window_hotspots(
            db,
            window=payload.window,
            now=datetime.now(),
            limit=int(payload.limit or 20),
            provider=payload.provider,
            use_llm=bool(payload.use_llm),
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"生成窗口热点失败：{exc}") from exc

    return WindowHotspotListResponse(window=payload.window, items=items)


@router.post(
    "/smart-filter",
    response_model=WindowHotspotListSmartFilterResponse,
    summary="窗口热点榜单智能筛选：按主题筛选相关事件",
)
def smart_filter_window_hotspot_list(
    payload: WindowHotspotListSmartFilterRequest,
    db: Session = Depends(deps.get_db),
) -> WindowHotspotListSmartFilterResponse:
    topic = (payload.topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic 不能为空")

    try:
        items = build_window_hotspots(
            db,
            window=payload.window,
            now=datetime.now(),
            limit=int(payload.limit or 50),
            provider=payload.provider,
            use_llm=False,
            start_time=payload.start_time,
            end_time=payload.end_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"获取窗口热点失败：{exc}") from exc

    if not items:
        return WindowHotspotListSmartFilterResponse(
            window=payload.window,
            topic=topic,
            recommended_event_keys=[],
            decisions=[],
        )

    # 中文说明：构造稳定的 event_key（前端用于过滤与跳转）
    keyed: list[tuple[str, dict]] = []
    for it in items:
        title = (it.get("title") or "").strip()
        te = (it.get("event_time_end") or "").strip()
        src0 = ((it.get("sources") or [{}])[0] or {})
        url0 = (src0.get("url") or "").strip()
        k = f"{(it.get('window') or payload.window or '').strip()}|{title}|{te}|{url0}"
        keyed.append((k, it))

    # prompt 中 id 用 index，避免把长 key 塞给模型
    events_for_prompt: list[dict] = []
    for idx, (_, it) in enumerate(keyed):
        events_for_prompt.append(
            {
                "id": idx,
                "title": it.get("title"),
                "summary": it.get("summary"),
                "hot_score": float(it.get("hot_score") or 0.0),
                "source_count": int(it.get("source_count") or 0),
            }
        )

    prompt = _build_window_list_smart_filter_prompt(
        window=payload.window,
        topic=topic,
        instruction=payload.instruction,
        events=events_for_prompt,
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

    recommended_keys: list[str] = []
    decisions = []
    for idx, (ek, _) in enumerate(keyed):
        meta = selected_map.get(idx)
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
            recommended_keys.append(ek)
        decisions.append(
            {
                "event_key": ek,
                "recommended": rec,
                "score": score,
                "reason": reason,
            }
        )

    return WindowHotspotListSmartFilterResponse(
        window=payload.window,
        topic=topic,
        recommended_event_keys=recommended_keys,
        decisions=decisions,
    )
