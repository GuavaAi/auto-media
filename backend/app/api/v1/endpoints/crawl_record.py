from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import os
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from bs4 import BeautifulSoup

from app import deps
from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent
from app.models.user import User
from app.schemas.crawl_record import (
    CrawlRecordDetailOut,
    CrawlRecordExtractMaterialsRequest,
    CrawlRecordExtractMaterialsResponse,
    CrawlRecordListResponse,
    CrawlRecordOut,
    CrawlRecordQuickFetchRequest,
    CrawlRecordQuickFetchResponse,
    CrawlRecordQuickFetchPreviewRequest,
    CrawlRecordQuickFetchPreviewResponse,
)
from app.services.api_key_pool import pick_api_key
from app.services.crawler import apply_parser, get_crawler_by_engine
from app.services.readability_extractor import extract_main_text
from app.services.text_cleaner import clean_text
from app.services.user_service import is_admin

router = APIRouter()


def _build_preview(content: str, max_len: int = 200) -> str:
    """构建内容预览：去掉多余空白并截断，避免列表接口返回超长文本。"""
    if content is None:
        return ""
    text = content.strip().replace("\r\n", "\n").replace("\r", "\n")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def _apply_css_selector_text(raw_html: str, css_selector: str) -> str:
    sel = (css_selector or "").strip()
    if not sel:
        return ""
    try:
        soup = BeautifulSoup(raw_html or "", "html.parser")
        nodes = soup.select(sel)
        if not nodes:
            return ""
        return "\n".join([n.get_text(separator="\n", strip=True) for n in nodes]).strip()
    except Exception:
        return ""


def _split_paragraphs(text: str) -> list[str]:
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in re.split(r"\n{2,}", t) if p and p.strip()]
    if parts:
        return parts
    return [p.strip() for p in t.split("\n") if p.strip()]


def _sentence_candidates(paragraph: str) -> list[str]:
    # 中文说明：用最轻量的方式把抓取内容切成“可做素材条目”的短句候选。
    p = (paragraph or "").replace("\r\n", "\n").replace("\r", "\n")
    p = re.sub(r"\s+", " ", p).strip()
    if not p:
        return []
    segs = re.split(r"[。！？!?；;]\s*", p)
    return [s.strip() for s in segs if s and len(s.strip()) >= 10]


def _score_sentence(s: str) -> float:
    # 中文说明：规则打分（非常粗）——长度 + 数字密度。
    s = s or ""
    base = min(len(s) / 80.0, 2.0)
    num_bonus = 0.6 if re.search(r"\d", s) else 0.0
    return base + num_bonus


def _norm_sentence(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _build_extract_items(
    *,
    content_id: int,
    url: str | None,
    title: str | None,
    text: str,
    top_k: int,
    include_source: bool,
):
    # 中文说明：返回 MaterialItemCreate 列表（不落库），供前端加入素材篮/写入素材包。
    from app.schemas.material import MaterialItemCreate

    cands: list[tuple[str, float]] = []
    for para in _split_paragraphs(text):
        for sent in _sentence_candidates(para):
            cands.append((sent, _score_sentence(sent)))
    cands.sort(key=lambda x: x[1], reverse=True)

    seen: set[str] = set()
    items: list[MaterialItemCreate] = []
    for s, _sc in cands:
        key = _norm_sentence(s)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(
            MaterialItemCreate(
                item_type="bullet",
                text=s,
                source_url=url,
                source_content_id=content_id,
                source_event_id=None,
                meta={"from": "crawl_record_extract"},
            )
        )
        if len(items) >= top_k:
            break

    if include_source and (url or title):
        text2 = " ".join([x for x in [(title or "").strip(), (url or "").strip()] if x]).strip()
        if text2:
            items.append(
                MaterialItemCreate(
                    item_type="source",
                    text=text2,
                    source_url=url,
                    source_content_id=content_id,
                    source_event_id=None,
                    meta={"from": "crawl_record_extract"},
                )
            )

    return items


def _resolve_firecrawl_key(db: Session) -> tuple[Optional[str], Optional[str]]:
    # 优先环境变量（兼容旧部署）；否则从 API Key 池轮询
    key = os.getenv("FIRECRAWL_API_KEY")
    base = os.getenv("FIRECRAWL_API_BASE")
    if key:
        return key, base
    ak = pick_api_key(db, "firecrawl", mark_used=True)
    if not ak:
        return None, base
    extra = ak.extra if isinstance(ak.extra, dict) else {}
    api_base = extra.get("api_base") if isinstance(extra, dict) else None
    return ak.key, (str(api_base).strip() if api_base else base)


@router.get("/", response_model=CrawlRecordListResponse, summary="抓取记录列表")
def list_crawl_records(
    datasource_id: Optional[int] = Query(None, description="按数据源筛选"),
    start_date: Optional[str] = Query(None, description="开始日期，YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期，YYYY-MM-DD"),
    limit: int = Query(20, ge=1, le=200, description="分页大小"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> CrawlRecordListResponse:
    # 列表查询：支持 datasource_id、日期范围筛选 + limit/offset 分页
    q = db.query(DataSourceContent)
    if not is_admin(current_user):
        q = q.filter(DataSourceContent.user_id == current_user.id)
    if datasource_id is not None:
        q = q.filter(DataSourceContent.datasource_id == datasource_id)

    # 日期范围：闭区间 [start, end]
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="start_date 格式需为 YYYY-MM-DD")
        q = q.filter(DataSourceContent.fetched_at >= start_dt)
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="end_date 格式需为 YYYY-MM-DD")
        q = q.filter(DataSourceContent.fetched_at < end_dt)

    total = q.count()
    rows = (
        q.order_by(desc(DataSourceContent.fetched_at), desc(DataSourceContent.id))
        .offset(offset)
        .limit(limit)
        .all()
    )

    # 为了前端展示友好，补充 datasource_name（避免前端额外请求 N 次）
    ds_ids = list({r.datasource_id for r in rows})
    name_map: dict[int, str] = {}
    if ds_ids:
        for ds in db.query(DataSource).filter(DataSource.id.in_(ds_ids)).all():
            name_map[ds.id] = ds.name

    items: list[CrawlRecordOut] = []
    for r in rows:
        display_title = None
        if isinstance(r.extra, dict):
            dt = r.extra.get("display_title")
            if isinstance(dt, str) and dt.strip():
                display_title = dt.strip()
        items.append(
            CrawlRecordOut(
                id=r.id,
                datasource_id=r.datasource_id,
                datasource_name=name_map.get(r.datasource_id),
                source_type=r.source_type,
                title=display_title or r.title,
                url=r.url,
                content_preview=_build_preview(r.content),
                extra=r.extra,
                fetched_at=r.fetched_at,
            )
        )

    return CrawlRecordListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/{record_id}", response_model=CrawlRecordDetailOut, summary="抓取记录详情")
def get_crawl_record(
    record_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> CrawlRecordDetailOut:
    q = db.query(DataSourceContent).filter(DataSourceContent.id == record_id)
    if not is_admin(current_user):
        q = q.filter(DataSourceContent.user_id == current_user.id)
    rec = q.first()
    if not rec:
        raise HTTPException(status_code=404, detail="抓取记录不存在")

    ds = db.query(DataSource).filter(DataSource.id == rec.datasource_id).first()
    ds_name = ds.name if ds else None

    display_title = None
    if isinstance(rec.extra, dict):
        dt = rec.extra.get("display_title")
        if isinstance(dt, str) and dt.strip():
            display_title = dt.strip()

    return CrawlRecordDetailOut(
        id=rec.id,
        datasource_id=rec.datasource_id,
        datasource_name=ds_name,
        source_type=rec.source_type,
        title=display_title or rec.title,
        url=rec.url,
        content_preview=_build_preview(rec.content),
        content=rec.content,
        extra=rec.extra,
        fetched_at=rec.fetched_at,
    )


@router.post(
    "/{record_id}/materials:extract",
    response_model=CrawlRecordExtractMaterialsResponse,
    summary="从抓取记录抽取素材条目（用于加入素材篮/写入素材包）",
)
def extract_crawl_record_materials(
    record_id: int,
    payload: CrawlRecordExtractMaterialsRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> CrawlRecordExtractMaterialsResponse:
    q = db.query(DataSourceContent).filter(DataSourceContent.id == record_id)
    if not is_admin(current_user):
        q = q.filter(DataSourceContent.user_id == current_user.id)
    rec = q.first()
    if not rec:
        raise HTTPException(status_code=404, detail="抓取记录不存在")

    text = (rec.content or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="抓取记录内容为空，无法抽取")

    top_k = int(payload.top_k or 8)
    top_k = max(1, min(50, top_k))
    include_source = bool(payload.include_source) if payload.include_source is not None else True

    items = _build_extract_items(
        content_id=rec.id,
        url=rec.url,
        title=rec.title,
        text=text,
        top_k=top_k,
        include_source=include_source,
    )
    return CrawlRecordExtractMaterialsResponse(items=items)


@router.post(
    "/quick-fetch",
    response_model=CrawlRecordQuickFetchResponse,
    summary="快捷抓取：针对单个 URL 做一次性抓取并生成抓取记录",
)
def quick_fetch(
    payload: CrawlRecordQuickFetchRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> CrawlRecordQuickFetchResponse:
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url 不能为空")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="url 必须以 http:// 或 https:// 开头")

    # 中文说明：快捷抓取统一归属到一个专用数据源，避免 datasource_id 为空
    ds_name = "快捷抓取"
    ds = db.query(DataSource).filter(DataSource.name == ds_name).first()
    if not ds:
        ds = DataSource(
            name=ds_name,
            source_type="url",
            config={"urls": []},
            enable_schedule=False,
            created_at=datetime.now(),
        )
        db.add(ds)
        db.flush()

    crawler_engine = (payload.crawler_engine or "").strip().lower() or "requests"
    use_playwright = bool(payload.use_playwright) if payload.use_playwright is not None else False
    if crawler_engine == "playwright":
        use_playwright = True
    timeout = int(payload.timeout or 30)
    timeout = max(5, min(180, timeout))
    css_selector = (payload.css_selector or "").strip() if hasattr(payload, "css_selector") else ""

    try:
        firecrawl_key = None
        firecrawl_base = None
        if crawler_engine == "firecrawl":
            firecrawl_key, firecrawl_base = _resolve_firecrawl_key(db)
            if not firecrawl_key:
                raise ValueError("FireCrawl API Key 未配置：请在 API Key 池中添加 provider=firecrawl 的 key，或设置环境变量 FIRECRAWL_API_KEY")

        crawler = get_crawler_by_engine(
            crawler_engine,
            use_playwright=use_playwright,
            firecrawl_api_key=firecrawl_key,
            firecrawl_api_base=firecrawl_base,
        )
        crawl_res = crawler.fetch(url, timeout=timeout)
        raw_html = crawl_res.html

        extract_res = extract_main_text(raw_html, None)
        content_text = extract_res.main_text
        if css_selector:
            picked = _apply_css_selector_text(raw_html, css_selector)
            if picked:
                content_text = picked

        clean_res = clean_text(content_text, None)
        content_hash_raw = hashlib.md5((content_text or "").encode("utf-8", "ignore")).hexdigest()
        url_hash = hashlib.md5(url.encode("utf-8", "ignore")).hexdigest()

        display_title = None
        if isinstance(extract_res.meta, dict):
            t = extract_res.meta.get("title")
            if isinstance(t, str) and t.strip():
                display_title = t.strip()

        rec = DataSourceContent(
            user_id=current_user.id,
            datasource_id=ds.id,
            source_type="url",
            title=display_title or url,
            url=url,
            url_hash=url_hash,
            content=clean_res.clean_text,
            extra={
                "status_code": crawl_res.status_code,
                "url": url,
                "final_url": (crawl_res.extra or {}).get("final_url") if crawl_res.extra else None,
                "crawler_engine": crawler_engine,
                "extractor": extract_res.extractor,
                "extractor_meta": extract_res.meta,
                "display_title": display_title,
                "content_hash": content_hash_raw,
                "clean_stats": clean_res.stats,
                "quality_flags": clean_res.quality_flags,
                "content_hash_clean": clean_res.content_hash_clean,
                "quick_fetch": True,
                "css_selector": css_selector or None,
            },
            fetched_at=datetime.now(),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"快捷抓取失败：{exc}") from exc

    return CrawlRecordQuickFetchResponse(
        id=rec.id,
        datasource_id=rec.datasource_id,
        datasource_name=ds.name,
        source_type=rec.source_type,
        title=display_title or rec.title,
        url=rec.url,
        content_preview=_build_preview(rec.content),
        extra=rec.extra,
        fetched_at=rec.fetched_at,
    )


@router.post(
    "/quick-fetch/preview",
    response_model=CrawlRecordQuickFetchPreviewResponse,
    summary="快捷抓取预览：抓取并返回正文预览（支持 CSS Selector）",
)
def quick_fetch_preview(
    payload: CrawlRecordQuickFetchPreviewRequest,
    db: Session = Depends(deps.get_db),
    _user: User = Depends(deps.require_user),
) -> CrawlRecordQuickFetchPreviewResponse:
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="url 不能为空")
    if not (url.startswith("http://") or url.startswith("https://")):
        raise HTTPException(status_code=400, detail="url 必须以 http:// 或 https:// 开头")

    crawler_engine = (payload.crawler_engine or "").strip().lower() or "requests"
    use_playwright = bool(payload.use_playwright) if payload.use_playwright is not None else False
    if crawler_engine == "playwright":
        use_playwright = True
    timeout = int(payload.timeout or 30)
    timeout = max(5, min(180, timeout))
    css_selector = (payload.css_selector or "").strip()

    try:
        firecrawl_key = None
        firecrawl_base = None
        if crawler_engine == "firecrawl":
            firecrawl_key, firecrawl_base = _resolve_firecrawl_key(db)
            if not firecrawl_key:
                raise ValueError("FireCrawl API Key 未配置：请在 API Key 池中添加 provider=firecrawl 的 key，或设置环境变量 FIRECRAWL_API_KEY")

        crawler = get_crawler_by_engine(
            crawler_engine,
            use_playwright=use_playwright,
            firecrawl_api_key=firecrawl_key,
            firecrawl_api_base=firecrawl_base,
        )
        crawl_res = crawler.fetch(url, timeout=timeout)
        raw_html = crawl_res.html
        extract_res = extract_main_text(raw_html, None)
        title = None
        if isinstance(extract_res.meta, dict):
            t = extract_res.meta.get("title")
            if isinstance(t, str) and t.strip():
                title = t.strip()

        content_text = extract_res.main_text
        if css_selector:
            picked = _apply_css_selector_text(raw_html, css_selector)
            if picked:
                content_text = picked

        clean_res = clean_text(content_text, None)
        text_preview = _build_preview(clean_res.clean_text, max_len=1200)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"预览失败：{exc}") from exc

    return CrawlRecordQuickFetchPreviewResponse(
        url=url,
        final_url=(crawl_res.extra or {}).get("final_url") if crawl_res.extra else None,
        status_code=crawl_res.status_code,
        title=title,
        extractor=extract_res.extractor,
        text_preview=text_preview,
    )
