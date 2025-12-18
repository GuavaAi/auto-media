from datetime import datetime, time
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app import deps
from app.models.article import Article
from app.models.datasource_content import DataSourceContent
from app.models.datasource import DataSource
from app.schemas.dashboard import DashboardRecentResponse, RecentArticle, RecentCrawlRecord, StatsResponse

router = APIRouter()

@router.get("/stats", response_model=StatsResponse, summary="首页统计数据")
def get_stats(db: Session = Depends(deps.get_db)):
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)

    total_articles = db.query(func.count(Article.id)).scalar() or 0
    today_articles = db.query(func.count(Article.id)).filter(Article.created_at >= today_start).scalar() or 0

    total_crawl = db.query(func.count(DataSourceContent.id)).scalar() or 0
    today_crawl = db.query(func.count(DataSourceContent.id)).filter(DataSourceContent.fetched_at >= today_start).scalar() or 0

    total_datasources = db.query(func.count(DataSource.id)).scalar() or 0

    return StatsResponse(
        total_articles=total_articles,
        today_articles=today_articles,
        total_crawl=total_crawl,
        today_crawl=today_crawl,
        total_datasources=total_datasources,
    )


@router.get("/recent", response_model=DashboardRecentResponse, summary="首页最近活动（文章/抓取）")
def get_recent(
    limit: int = Query(5, ge=1, le=50, description="返回条数"),
    db: Session = Depends(deps.get_db),
) -> DashboardRecentResponse:
    # 最近文章
    art_rows = (
        db.query(Article)
        .order_by(Article.created_at.desc(), Article.id.desc())
        .limit(limit)
        .all()
    )
    recent_articles = [
        RecentArticle(
            id=a.id,
            title=a.title,
            summary=a.summary,
            llm_provider=a.llm_provider,
            llm_model=a.llm_model,
            elapsed_ms=a.elapsed_ms,
            created_at=a.created_at,
        )
        for a in art_rows
    ]

    # 最近抓取记录 + datasource_name
    rec_rows = (
        db.query(DataSourceContent)
        .order_by(DataSourceContent.fetched_at.desc(), DataSourceContent.id.desc())
        .limit(limit)
        .all()
    )
    ds_ids = list({r.datasource_id for r in rec_rows if r.datasource_id is not None})
    name_map: dict[int, str] = {}
    if ds_ids:
        for ds in db.query(DataSource).filter(DataSource.id.in_(ds_ids)).all():
            name_map[ds.id] = ds.name

    recent_crawl_records = [
        RecentCrawlRecord(
            id=r.id,
            datasource_id=r.datasource_id,
            datasource_name=name_map.get(r.datasource_id),
            title=r.title,
            url=r.url,
            fetched_at=r.fetched_at,
            extra=r.extra,
        )
        for r in rec_rows
    ]

    return DashboardRecentResponse(
        recent_articles=recent_articles,
        recent_crawl_records=recent_crawl_records,
    )
