from __future__ import annotations

from datetime import datetime

from celery import shared_task

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.window_hotspot_builder import build_window_hotspots


def _parse_windows(raw: str | None) -> list[str]:
    s = (raw or "").strip()
    if not s:
        return ["today"]
    out: list[str] = []
    for x in s.split(","):
        t = x.strip()
        if not t:
            continue
        out.append(t)
    return out or ["today"]


@shared_task(name="app.tasks.window_hotspots.build_window_hotspots_task")
def build_window_hotspots_task() -> dict:
    """Celery 任务：定时预热窗口热点（不落库）。

    中文说明：
    - 当前窗口热点是实时计算（不落库），定时任务的作用是“预热/健康检查”。
    - 运营侧若需要真正的缓存，可在此任务中把结果写入 Redis（后续可扩展）。
    """

    settings = get_settings()

    windows = _parse_windows(getattr(settings, "WINDOW_HOTSPOT_WINDOWS", None))
    limit = int(getattr(settings, "WINDOW_HOTSPOT_LIMIT", 20) or 20)
    use_llm = bool(getattr(settings, "WINDOW_HOTSPOT_USE_LLM", False))
    provider = getattr(settings, "WINDOW_HOTSPOT_PROVIDER", None)

    db = SessionLocal()
    try:
        now = datetime.now()
        results: dict[str, int] = {}
        total = 0
        for w in windows:
            items = build_window_hotspots(
                db,
                window=w,
                now=now,
                limit=limit,
                provider=provider,
                use_llm=use_llm,
            )
            results[w] = len(items or [])
            total += len(items or [])

        if total <= 0:
            return {"status": "skipped", "window_counts": results, "total": total}

        return {"status": "ok", "window_counts": results, "total": total}
    except ValueError as e:
        # 中文说明：参数不合法或无数据等业务错误，不算系统失败
        return {"status": "skipped", "reason": str(e)}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}
    finally:
        db.close()
