from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "auto_media",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.daily_hotspots",
        "app.tasks.publish",
        "app.tasks.morning_brief",
        "app.tasks.datasource",  # 数据源定时扫描与触发
    ],
)

celery_app.conf.update(
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=False,
)

if settings.CELERY_ALWAYS_EAGER:
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )

# 初始化 beat_schedule，后续按条件增补
celery_app.conf.beat_schedule = {}

# Beat 定时任务配置（阶段2：每天跑批生成热点榜单）
if settings.DAILY_HOTSPOT_BEAT_ENABLED:
    parts = [p.strip() for p in (settings.DAILY_HOTSPOT_CRON or "").split() if p.strip()]
    if len(parts) != 5:
        raise ValueError("DAILY_HOTSPOT_CRON 格式错误，需为 5 段 cron：minute hour dom month dow")

    minute, hour, day_of_month, month_of_year, day_of_week = parts

    celery_app.conf.beat_schedule = {
        "build-daily-hotspots": {
            "task": "app.tasks.daily_hotspots.build_daily_hotspots_task",
            "schedule": crontab(
                minute=minute,
                hour=hour,
                day_of_month=day_of_month,
                month_of_year=month_of_year,
                day_of_week=day_of_week,
            ),
            "options": {"queue": "default"},
        }
    }

    # Morning Brief (Scenario C)
    if settings.MORNING_BRIEF_ENABLED:
        mb_parts = [p.strip() for p in (settings.MORNING_BRIEF_CRON or "").split() if p.strip()]
        if len(mb_parts) == 5:
            mb_min, mb_hour, mb_dom, mb_mon, mb_dow = mb_parts
            celery_app.conf.beat_schedule["morning-brief-task"] = {
                "task": "app.tasks.morning_brief.run_morning_brief_task",
                "schedule": crontab(
                    minute=mb_min,
                    hour=mb_hour,
                    day_of_month=mb_dom,
                    month_of_year=mb_mon,
                    day_of_week=mb_dow,
                ),
                "options": {"queue": "default"},
            }

# 数据源定时扫描任务：每 1 分钟检查一次到期的数据源并触发抓取
celery_app.conf.beat_schedule["scan-datasource-schedule"] = {
    "task": "app.tasks.datasource.scan_and_trigger_datasources",
    "schedule": crontab(minute="*/1"),
    "options": {"queue": "default"},
}
