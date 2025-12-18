from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session

from app import deps
from app.models.event_cluster import EventCluster
from app.schemas.article import ArticleOut, GenerationRequest
from app.services.generation import generate_article

router = APIRouter()


@router.post(
    "/from-event/{event_id}",
    response_model=ArticleOut,
    summary="热点一键生成草稿 (Quick Draft)",
)
def quick_generate_from_event(
    event_id: int,
    db: Session = Depends(deps.get_db),
) -> ArticleOut:
    """
    根据热点事件 ID，自动组装素材与 Prompt，一键生成文章草稿。
    """
    event = db.query(EventCluster).filter(EventCluster.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="热点事件不存在")

    # 构造请求
    # 注意：这里隐式使用了默认模型与默认模板
    req = GenerationRequest(
        topic=event.title or "今日热点",
        summary_hint=event.summary,
        source_event_id=event_id,
        # 默认参数，后续可从配置读取
        tone="专业且亲和",
        length=1200,
        temperature=0.7,
    )
    
    try:
        return generate_article(db, req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/from-topic",
    response_model=ArticleOut,
    summary="主题实时生成 (Active Inspiration)",
)
def quick_generate_from_topic(
    topic: str = Body(..., embed=True),
    db: Session = Depends(deps.get_db),
) -> ArticleOut:
    """
    根据自定义主题，实时调用 Firecrawl 搜索素材并生成草稿。
    """
    if not topic or not topic.strip():
        raise HTTPException(status_code=400, detail="主题不能为空")

    req = GenerationRequest(
        topic=topic.strip(),
        source_query=topic.strip(),
        # 默认配置
        tone="深度且有即时感",
        length=1500,
        temperature=0.75,
    )

    try:
        # 这个过程可能会比较慢 (Firecrawl search + LLM generate)，建议前端做好 Loading
        return generate_article(db, req)
    except RuntimeError as exc:
        # Firecrawl 错误
        raise HTTPException(status_code=502, detail=f"搜索服务暂不可用: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
