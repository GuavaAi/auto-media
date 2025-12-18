from __future__ import annotations

from datetime import date, timedelta

from celery import shared_task

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.daily_hotspot_builder import build_daily_hotspots


def _calc_target_day(today: date) -> date:
    # 默认生成昨天榜单（凌晨跑批更合理）
    settings = get_settings()
    return today + timedelta(days=int(settings.DAILY_HOTSPOT_DAY_OFFSET or 0))


@shared_task(name="app.tasks.daily_hotspots.build_daily_hotspots_task")
def build_daily_hotspots_task() -> dict:
    """Celery 任务：按配置生成某日热点榜单（TopN）。

    - 目标日期通过 DAILY_HOTSPOT_DAY_OFFSET 控制
    - 若当天无采集数据则跳过（不算失败）
    """

    settings = get_settings()
    target_day = _calc_target_day(date.today())

    db = SessionLocal()
    try:
        events = build_daily_hotspots(db, day=target_day, limit=int(settings.DAILY_HOTSPOT_LIMIT or 20))
        db.commit()
        return {
            "status": "ok",
            "day": target_day.isoformat(),
            "event_count": len(events),
        }
    except ValueError as e:
        db.rollback()
        return {
            "status": "skipped",
            "day": target_day.isoformat(),
            "reason": str(e),
        }
    finally:
        db.close()
