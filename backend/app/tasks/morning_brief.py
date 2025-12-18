from __future__ import annotations

from datetime import date, timedelta
from celery import shared_task
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.event_cluster import EventCluster
from app.schemas.article import GenerationRequest
from app.services.daily_hotspot_builder import build_daily_hotspots
from app.services.generation import generate_article


def _calc_target_day(today: date) -> date:
    # 默认生成昨天榜单（凌晨跑批更合理）
    settings = get_settings()
    return today + timedelta(days=int(settings.DAILY_HOTSPOT_DAY_OFFSET or 0))


def _get_top_events(db: Session, day: date, limit: int = 3) -> list[EventCluster]:
    """获取指定日期热度最高的 Top N 事件"""
    return (
        db.query(EventCluster)
        .filter(EventCluster.day == day)
        .order_by(EventCluster.hot_score.desc())
        .limit(limit)
        .all()
    )


@shared_task(name="app.tasks.morning_brief.run_morning_brief_task")
def run_morning_brief_task() -> dict:
    """
    Morning Brief 自动化任务：
    1. 自动构建今日（或指定日期）热点榜单
    2. 选取 Top 3 事件
    3. 分别生成【深度分析】、【辛辣点评】、【资讯快报】三种风格的草稿
    """
    settings = get_settings()
    # 复用 daily_hotspots 的日期计算逻辑（通常是 yesterday）
    # 但 Morning Brief 是早上 7 点跑，可能想要的是 "今天" 的早报（基于昨天的数据）
    target_day = _calc_target_day(date.today())

    db = SessionLocal()
    result = {
        "status": "ok",
        "day": target_day.isoformat(),
        "generated_articles": [],
        "errors": [],
    }

    try:
        # 1. 确保热点榜单已构建 (幂等)
        # Limit 设大一点，确保能选出 Top 3
        build_daily_hotspots(db, day=target_day, limit=max(20, int(settings.DAILY_HOTSPOT_LIMIT or 20)))
        db.commit()

        # 2. 获取 Top 3
        top_events = _get_top_events(db, target_day, limit=3)
        if not top_events:
            result["status"] = "skipped_no_events"
            return result

        # 3. 定义风格策略 (按排名分配)
        # Rank 1 -> Deep Analysis
        # Rank 2 -> Spicy Comment
        # Rank 3 -> Fast News
        styles = [
            {"tone": "深度分析", "length": 2000, "suffix": "【深度】"},
            {"tone": "辛辣点评", "length": 1200, "suffix": "【辣评】"},
            {"tone": "资讯快报", "length": 800, "suffix": "【快讯】"},
        ]

        # 循环生成
        for i, event in enumerate(top_events):
            if i >= len(styles):
                break
                
            style = styles[i]
            
            # 构造生成请求
            req = GenerationRequest(
                topic=f"{event.title} {style['suffix']}", # 标题加上后缀区分
                summary_hint=f"基于{event.title}，进行{style['tone']}。{event.summary}",
                source_event_id=event.id,
                tone=style["tone"],
                length=style["length"],
                temperature=0.75, # 稍微高一点，增加多样性
            )

            try:
                article = generate_article(db, req)
                result["generated_articles"].append({
                    "id": article.id,
                    "title": article.title,
                    "style": style["tone"]
                })
            except Exception as exc:
                err_msg = f"Event {event.id} ({style['tone']}) generation failed: {str(exc)}"
                result["errors"].append(err_msg)
                # 继续处理下一个，不中断整个任务

        return result

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
