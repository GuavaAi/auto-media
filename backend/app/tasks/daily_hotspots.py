from __future__ import annotations

from datetime import date, timedelta

from celery import shared_task

from app.core.config import get_settings
from app.tasks.window_hotspots import build_window_hotspots_task


def _calc_target_day(today: date) -> date:
    # 默认生成昨天榜单（凌晨跑批更合理）
    settings = get_settings()
    return today + timedelta(days=int(settings.DAILY_HOTSPOT_DAY_OFFSET or 0))


@shared_task(name="app.tasks.daily_hotspots.build_daily_hotspots_task")
def build_daily_hotspots_task() -> dict:
    """兼容任务：历史日榜任务入口（已废弃）。

    中文说明：
    - 前端与产品逻辑已切换到“窗口热点”（实时计算、不落库）
    - 这里保留同名 task，避免旧的 beat/运维脚本仍调用导致报错
    - 实际执行窗口热点预热任务 build_window_hotspots_task
    """

    # 保留 day 字段以兼容旧监控面板/日志格式
    target_day = _calc_target_day(date.today())

    res = build_window_hotspots_task()
    status = res.get("status") or "ok"
    return {
        "status": status,
        "day": target_day.isoformat(),
        "window_counts": res.get("window_counts"),
        "total": res.get("total"),
        "reason": res.get("reason"),
    }
