from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
import hashlib
import concurrent.futures
import time
from urllib.parse import urljoin, urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException
from requests import RequestException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc

from app.services.crawler import (
    get_crawler,
    get_crawler_by_engine,
    apply_parser,
    discover_links,
)
from app.services.api_key_pool import pick_api_key
from app.services.text_cleaner import clean_text
from app.services.readability_extractor import extract_main_text

from app import deps
from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceOut,
    DataSourceUpdate,
)

router = APIRouter()


def _normalize_firecrawl_base(base: str | None) -> str:
    b = (base or "https://api.firecrawl.dev/v1").rstrip("/")
    if b.endswith("/v2"):
        return b
    if b.endswith("/v2/search"):
        return b[: -len("/search")]
    if b.endswith("/v1"):
        return b[: -len("/v1")] + "/v2"
    return b + "/v2"


@router.get("/", response_model=List[DataSourceOut], summary="数据源列表")
def list_datasources(db: Session = Depends(deps.get_db)) -> list[DataSource]:
    """列出所有数据源"""
    return db.query(DataSource).order_by(DataSource.id.desc()).all()


@router.post("/", response_model=DataSourceOut, summary="新增数据源")
def create_datasource(
    payload: DataSourceCreate, db: Session = Depends(deps.get_db)
) -> DataSource:
    """创建数据源，支持不同类型的采集配置"""
    exists = (
        db.query(DataSource).filter(DataSource.name == payload.name).first()
        if payload.name
        else None
    )
    if exists:
        raise HTTPException(status_code=400, detail="数据源名称已存在")
    ds = DataSource(
        name=payload.name,
        source_type=payload.source_type,
        config=payload.config,
        biz_category=payload.biz_category,
        schedule_cron=payload.schedule_cron,
        enable_schedule=payload.enable_schedule,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.delete("/{ds_id}", summary="删除数据源")
def delete_datasource(ds_id: int, db: Session = Depends(deps.get_db)) -> dict:
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")
    db.delete(ds)
    db.commit()
    return {"success": True}


@router.put("/{ds_id}", response_model=DataSourceOut, summary="更新数据源")
def update_datasource(
    ds_id: int, payload: DataSourceUpdate, db: Session = Depends(deps.get_db)
) -> DataSource:
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    if payload.name and payload.name != ds.name:
        exists = (
            db.query(DataSource)
            .filter(DataSource.name == payload.name, DataSource.id != ds_id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=400, detail="数据源名称已存在")

    ds.name = payload.name or ds.name
    ds.source_type = payload.source_type or ds.source_type
    ds.config = payload.config or ds.config
    ds.biz_category = payload.biz_category
    ds.schedule_cron = payload.schedule_cron
    ds.enable_schedule = payload.enable_schedule

    db.commit()
    db.refresh(ds)
    return ds


@router.post("/{ds_id}/trigger", response_model=DataSourceOut, summary="手动触发采集并入库原始内容")
def trigger_datasource(
    ds_id: int, force: bool = False, db: Session = Depends(deps.get_db)
) -> DataSource:
    """
    手动触发采集：更新 last_run_at，并可选调用 n8n webhook。
    后续可在此接入实际抓取逻辑或任务队列。
    """
    ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    now_local = datetime.now()  # 存库使用本地时间（建议服务器时区为 Asia/Shanghai）
    now_naive = now_local
    cfg = ds.config if isinstance(ds.config, dict) else {}

    # 中文说明：用于把本次 trigger 的统计信息写回 datasource.config，便于前端查看。
    last_trigger_report: dict = {}

    def compute_next_run(cron_expr: str | None, start_dt: datetime) -> datetime | None:
        if not cron_expr:
            return None
        try:
            from croniter import croniter
        except ImportError:
            return start_dt + timedelta(hours=1)
        try:
            itr = croniter(cron_expr, start_dt)
            return itr.get_next(datetime)
        except Exception:
            return None

    def fetch_urls() -> list[DataSourceContent]:
        urls = cfg.get("urls") if isinstance(cfg, dict) else None
        pagination_cfg = cfg.get("pagination") if isinstance(cfg, dict) else None
        auto_discover = bool(cfg.get("auto_discover_sub", True)) if isinstance(cfg, dict) else True
        max_sub_links = int(cfg.get("max_sub_links", 10) or 10) if isinstance(cfg, dict) else 10
        headers = cfg.get("headers") if isinstance(cfg, dict) else None
        parser_cfg = cfg.get("parser") if isinstance(cfg, dict) else None
        sub_parser_cfg_raw = cfg.get("sub_parser") if isinstance(cfg, dict) else None
        use_playwright = bool(cfg.get("use_playwright")) if isinstance(cfg, dict) else False
        crawler_engine = str(cfg.get("crawler_engine") or "").strip() if isinstance(cfg, dict) else ""
        firecrawl_api_key = cfg.get("firecrawl_api_key") if isinstance(cfg, dict) else None
        firecrawl_api_base = cfg.get("firecrawl_api_base") if isinstance(cfg, dict) else None
        firecrawl_scrape = cfg.get("firecrawl_scrape") if isinstance(cfg, dict) else None
        firecrawl_batch = cfg.get("firecrawl_batch") if isinstance(cfg, dict) else None
        crawl4ai_options = (
            cfg.get("crawl4ai_options") if isinstance(cfg, dict) else None
        )
        engine_lower = crawler_engine.lower()
        if not urls or not isinstance(urls, list):
            raise HTTPException(status_code=400, detail="url 类型需提供 urls 列表")

        # 子页面过滤：只支持 css_selector，不做关键词过滤
        sub_parser_cfg = None
        if isinstance(sub_parser_cfg_raw, dict):
            css = sub_parser_cfg_raw.get("css_selector")
            if isinstance(css, str) and css.strip():
                sub_parser_cfg = {"css_selector": css.strip()}
        if sub_parser_cfg is None and isinstance(parser_cfg, dict):
            css = parser_cfg.get("css_selector")
            if isinstance(css, str) and css.strip():
                sub_parser_cfg = {"css_selector": css.strip()}

        # 中文说明：Firecrawl 的 batch 抓取不支持本项目的“动态发现子页面”，避免混用导致行为不一致。
        use_firecrawl_batch = (
            engine_lower == "firecrawl"
            and isinstance(firecrawl_batch, dict)
            and bool(firecrawl_batch.get("enabled"))
        )
        if use_firecrawl_batch:
            auto_discover = False

        # 构建抓取队列：主 URL + 分页
        full_urls: list[tuple[str, bool]] = []
        seen = set()
        for u in urls:
            if isinstance(u, str) and u.strip() and u not in seen:
                full_urls.append((u, False))
                seen.add(u)
        if pagination_cfg and isinstance(pagination_cfg, dict):
            base_url = pagination_cfg.get("base_url")
            page_param = pagination_cfg.get("page_param", "page")
            start = int(pagination_cfg.get("start", 1) or 1)
            end = int(pagination_cfg.get("end", start))
            if base_url:
                for page in range(start, end + 1):
                    if "?" in base_url:
                        page_url = f"{base_url}&{page_param}={page}"
                    else:
                        page_url = f"{base_url}?{page_param}={page}"
                    if page_url not in seen:
                        full_urls.append((page_url, False))
                        seen.add(page_url)

        results: list[DataSourceContent] = []
        discover_budget = max_sub_links
        idx = 0
        if engine_lower == "firecrawl" and not (firecrawl_api_key or "").strip():
            picked = pick_api_key(db, "firecrawl", mark_used=True)
            if picked:
                firecrawl_api_key = (picked.key or "").strip()

        crawler = get_crawler_by_engine(
            crawler_engine,
            use_playwright=use_playwright,
            firecrawl_api_key=firecrawl_api_key,
            firecrawl_api_base=firecrawl_api_base,
            firecrawl_options=firecrawl_scrape if isinstance(firecrawl_scrape, dict) else None,
            crawl4ai_options=crawl4ai_options if isinstance(crawl4ai_options, dict) else None,
        )
        subpage_urls: list[str] = []

        stats = {
            "dedup_skipped": 0,
            "empty_skipped": 0,
            "fetch_failed": 0,
        }

        skipped_details: list[dict] = []

        extractor_cfg = cfg.get("extractor") if isinstance(cfg, dict) else None
        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        sub_concurrency = int(cfg.get("sub_concurrency", 6) or 6) if isinstance(cfg, dict) else 6

        def _build_record(
            *,
            url_str: str,
            clean_res,
            content_hash_raw: str,
            status_code: int | None,
            final_url: str | None,
            extractor_name: str,
            display_title: str | None,
            extractor_meta: dict | None,
            extra_more: dict | None = None,
        ) -> DataSourceContent | None:
            # 增量爬取：若最新一条内容的 hash 相同，则跳过入库
            url_hash = hashlib.md5(str(url_str).encode("utf-8", "ignore")).hexdigest()
            last_rec = (
                db.query(DataSourceContent)
                .filter(
                    DataSourceContent.datasource_id == ds.id,
                    DataSourceContent.url_hash == url_hash,
                )
                .order_by(desc(DataSourceContent.fetched_at))
                .first()
            )
            if (not force) and last_rec and isinstance(last_rec.extra, dict):
                if (
                    last_rec.extra.get("content_hash_clean")
                    and last_rec.extra.get("content_hash_clean")
                    == clean_res.content_hash_clean
                ):
                    stats["dedup_skipped"] += 1
                    skipped_details.append(
                        {
                            "url": str(url_str),
                            "reason": "dedup_hash_clean_same",
                            "matched_record_id": last_rec.id,
                            "matched_fetched_at": last_rec.fetched_at.isoformat() if last_rec.fetched_at else None,
                        }
                    )
                    return None
                if last_rec.extra.get("content_hash") == content_hash_raw:
                    stats["dedup_skipped"] += 1
                    skipped_details.append(
                        {
                            "url": str(url_str),
                            "reason": "dedup_hash_raw_same",
                            "matched_record_id": last_rec.id,
                            "matched_fetched_at": last_rec.fetched_at.isoformat() if last_rec.fetched_at else None,
                        }
                    )
                    return None

            real_title = None
            if isinstance(extractor_meta, dict):
                t = extractor_meta.get("title")
                if isinstance(t, str) and t.strip():
                    real_title = t.strip()

            return DataSourceContent(
                datasource_id=ds.id,
                source_type="url",
                # title 字段用于展示：优先使用抽取到的真实标题
                title=real_title or str(url_str),
                url=str(url_str),
                url_hash=url_hash,
                content=clean_res.clean_text,
                extra={
                    "status_code": status_code,
                    "url": url_str,
                    "headers": headers,
                    "parser": cfg.get("parser"),
                    "extractor": extractor_name,
                    "extractor_meta": extractor_meta,
                    # 用于前端展示的标题（优先 Readability 提取到的 title）
                    "display_title": display_title,
                    "content_hash": content_hash_raw,
                    "content_hash_clean": clean_res.content_hash_clean,
                    "clean_stats": clean_res.stats,
                    "quality_flags": clean_res.quality_flags,
                    "final_url": final_url,
                    **(extra_more or {}),
                },
                fetched_at=now_naive,
            )

        def _firecrawl_batch_scrape(url_list: list[str]) -> list[dict[str, Any]]:
            nonlocal firecrawl_api_key
            if not (firecrawl_api_key or "").strip():
                raise HTTPException(status_code=400, detail="FireCrawl 抓取未配置可用 API Key")

            batch_cfg = firecrawl_batch if isinstance(firecrawl_batch, dict) else {}
            scrape_cfg = firecrawl_scrape if isinstance(firecrawl_scrape, dict) else {}

            formats = scrape_cfg.get("formats") or scrape_cfg.get("scrape_formats") or ["html"]
            if not isinstance(formats, list) or not formats:
                formats = ["html"]

            body: dict[str, Any] = {
                "urls": url_list,
                "formats": formats,
                "ignoreInvalidURLs": bool(batch_cfg.get("ignore_invalid_urls", True)),
            }

            if isinstance(scrape_cfg.get("onlyMainContent"), bool):
                body["onlyMainContent"] = bool(scrape_cfg.get("onlyMainContent"))
            elif isinstance(scrape_cfg.get("only_main_content"), bool):
                body["onlyMainContent"] = bool(scrape_cfg.get("only_main_content"))

            max_age = scrape_cfg.get("maxAge") if scrape_cfg.get("maxAge") is not None else scrape_cfg.get("max_age")
            try:
                max_age_int = int(max_age) if max_age is not None else None
            except Exception:
                max_age_int = None
            if max_age_int is not None and max_age_int >= 0:
                body["maxAge"] = max_age_int

            wait_for = scrape_cfg.get("waitFor") if scrape_cfg.get("waitFor") is not None else scrape_cfg.get("wait_for")
            try:
                wait_for_int = int(wait_for) if wait_for is not None else None
            except Exception:
                wait_for_int = None
            if wait_for_int is not None and wait_for_int >= 0:
                body["waitFor"] = wait_for_int

            if isinstance(scrape_cfg.get("headers"), dict):
                body["headers"] = scrape_cfg.get("headers")
            elif isinstance(headers, dict) and headers:
                body["headers"] = headers

            max_conc = batch_cfg.get("max_concurrency") if batch_cfg.get("max_concurrency") is not None else batch_cfg.get("maxConcurrency")
            try:
                max_conc_int = int(max_conc) if max_conc is not None else None
            except Exception:
                max_conc_int = None
            if max_conc_int is not None and max_conc_int > 0:
                body["maxConcurrency"] = max_conc_int

            base_v2 = _normalize_firecrawl_base(firecrawl_api_base)
            endpoint = base_v2.rstrip("/") + "/batch/scrape"
            req_headers = {
                "Authorization": f"Bearer {firecrawl_api_key}",
                "Content-Type": "application/json",
            }

            try:
                resp = requests.post(endpoint, json=body, headers=req_headers, timeout=120)
                resp.raise_for_status()
                jd = resp.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"FireCrawl 批量抓取创建失败：{exc}") from exc

            # 兼容同步直接返回 data
            if isinstance(jd, dict) and isinstance(jd.get("data"), list):
                return jd.get("data")

            if not isinstance(jd, dict) or not jd.get("success") or not jd.get("id"):
                raise HTTPException(status_code=400, detail=f"FireCrawl 批量抓取返回异常：{jd}")

            job_id = str(jd.get("id"))
            status_ep = base_v2.rstrip("/") + f"/batch/scrape/{job_id}"
            deadline = datetime.now().timestamp() + 180
            last_jd: dict | None = None
            while datetime.now().timestamp() < deadline:
                try:
                    r2 = requests.get(status_ep, headers={"Authorization": f"Bearer {firecrawl_api_key}"}, timeout=30)
                    r2.raise_for_status()
                    last_jd = r2.json()
                except Exception:
                    last_jd = None

                if isinstance(last_jd, dict):
                    st = str(last_jd.get("status") or "").lower()
                    if st == "completed":
                        data = last_jd.get("data")
                        return data if isinstance(data, list) else []
                    if st == "failed":
                        raise HTTPException(status_code=400, detail=f"FireCrawl 批量抓取失败：{last_jd}")

                time.sleep(2)

            raise HTTPException(status_code=400, detail="FireCrawl 批量抓取超时")

        if use_firecrawl_batch:
            url_list = [u for (u, is_sub) in full_urls if isinstance(u, str) and u.strip() and not is_sub]
            items = _firecrawl_batch_scrape(url_list)
            for it in items:
                try:
                    if not isinstance(it, dict):
                        continue
                    meta = it.get("metadata") if isinstance(it.get("metadata"), dict) else {}
                    url_str = meta.get("sourceURL") or it.get("url")
                    if not isinstance(url_str, str) or not url_str.strip():
                        continue
                    url_str = url_str.strip()
                    raw_html = it.get("html") or it.get("rawHtml") or it.get("markdown") or ""
                    if not isinstance(raw_html, str) or not raw_html.strip():
                        continue

                    extract_res = extract_main_text(raw_html, extractor_cfg if isinstance(extractor_cfg, dict) else None)
                    content_text = apply_parser(extract_res.main_text, parser_cfg)
                    if content_text == "":
                        stats["empty_skipped"] += 1
                        skipped_details.append({"url": url_str, "reason": "empty"})
                        continue

                    clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                    content_hash = hashlib.md5(content_text.encode("utf-8", "ignore")).hexdigest()

                    status_code = meta.get("statusCode") if isinstance(meta, dict) else None
                    try:
                        status_code_int = int(status_code) if status_code is not None else None
                    except Exception:
                        status_code_int = None

                    rec = _build_record(
                        url_str=url_str,
                        clean_res=clean_res,
                        content_hash_raw=content_hash,
                        status_code=status_code_int,
                        final_url=meta.get("sourceURL") if isinstance(meta, dict) else None,
                        extractor_name=extract_res.extractor,
                        display_title=(meta.get("title") if isinstance(meta, dict) else None),
                        extractor_meta=extract_res.meta if isinstance(extract_res.meta, dict) else None,
                        extra_more={
                            "firecrawl_mode": "batch_scrape",
                            "firecrawl_metadata": meta if isinstance(meta, dict) else None,
                        },
                    )
                    if rec:
                        results.append(rec)
                except Exception:
                    stats["fetch_failed"] += 1
                    continue

            if not results:
                if stats["dedup_skipped"] > 0 and stats["fetch_failed"] == 0:
                    last_trigger_report.update({"stats": stats, "skipped_details": skipped_details})
                    return []
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "FireCrawl 批量抓取无有效内容，请检查 URL/网络/额度。"
                        f"(dedup={stats['dedup_skipped']}, empty={stats['empty_skipped']}, failed={stats['fetch_failed']})"
                    ),
                )

            last_trigger_report.update({"stats": stats, "skipped_details": skipped_details})
            return results

        results: list[DataSourceContent] = []
        discover_budget = max_sub_links
        idx = 0
        while idx < len(full_urls):
            url, is_sub_page = full_urls[idx]
            idx += 1
            if is_sub_page:
                # 子页面统一放到后面的并发阶段处理
                if url not in seen:
                    seen.add(url)
                subpage_urls.append(url)
                continue

            try:
                crawl_result = crawler.fetch(url, headers=headers, timeout=20)
                raw_html = crawl_result.html

                # 正文抽取 + 过滤
                extract_res = extract_main_text(
                    raw_html,
                    extractor_cfg if isinstance(extractor_cfg, dict) else None,
                )
                content_text = apply_parser(extract_res.main_text, parser_cfg)
                if content_text == "":
                    stats["empty_skipped"] += 1
                    skipped_details.append({"url": url, "reason": "empty"})
                    continue

                clean_res = clean_text(
                    content_text,
                    cleaner_cfg if isinstance(cleaner_cfg, dict) else None,
                )
                content_hash = hashlib.md5(
                    content_text.encode("utf-8", "ignore")
                ).hexdigest()

                display_title = None
                if isinstance(extract_res.meta, dict):
                    t = extract_res.meta.get("title")
                    if isinstance(t, str) and t.strip():
                        display_title = t.strip()

                rec = _build_record(
                    url_str=url,
                    clean_res=clean_res,
                    content_hash_raw=content_hash,
                    status_code=crawl_result.status_code,
                    final_url=(crawl_result.extra or {}).get("final_url") if crawl_result.extra else None,
                    extractor_name=extract_res.extractor,
                    display_title=display_title,
                    extractor_meta=extract_res.meta if isinstance(extract_res.meta, dict) else None,
                )
                if rec:
                    results.append(rec)

                # 动态发现子页面（同域），受 budget 限制；仅从主页面发现
                if auto_discover and discover_budget > 0:
                    new_links = discover_links(
                        raw_html,
                        url,
                        discover_budget,
                        seen,
                        parser_cfg,
                    )
                    for link in new_links:
                        seen.add(link)
                        subpage_urls.append(link)
                    discover_budget -= len(new_links)
            except RequestException:
                stats["fetch_failed"] += 1
                skipped_details.append({"url": url, "reason": "fetch_failed"})
                continue

        # 子页面并发抓取（只抓取，不再继续发现子页面）
        def _fetch_subpage(url_str: str):
            crawl_result = crawler.fetch(url_str, headers=headers, timeout=20)
            raw_html = crawl_result.html
            extract_res = extract_main_text(
                raw_html,
                extractor_cfg if isinstance(extractor_cfg, dict) else None,
            )
            content_text = apply_parser(extract_res.main_text, sub_parser_cfg)
            if content_text == "":
                return {"skip": "empty", "url": url_str}
            clean_res = clean_text(
                content_text,
                cleaner_cfg if isinstance(cleaner_cfg, dict) else None,
            )
            content_hash = hashlib.md5(
                content_text.encode("utf-8", "ignore")
            ).hexdigest()
            display_title = None
            if isinstance(extract_res.meta, dict):
                t = extract_res.meta.get("title")
                if isinstance(t, str) and t.strip():
                    display_title = t.strip()
            return {
                "url": url_str,
                "clean_res": clean_res,
                "content_hash": content_hash,
                "status_code": crawl_result.status_code,
                "final_url": (crawl_result.extra or {}).get("final_url") if crawl_result.extra else None,
                "extractor": extract_res.extractor,
                "display_title": display_title,
                "extractor_meta": extract_res.meta if isinstance(extract_res.meta, dict) else None,
            }

        if subpage_urls:
            workers = max(1, min(32, sub_concurrency))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(_fetch_subpage, u) for u in subpage_urls]
                for fut in concurrent.futures.as_completed(futs):
                    try:
                        payload = fut.result()
                    except Exception:
                        stats["fetch_failed"] += 1
                        continue
                    if not payload:
                        continue
                    if isinstance(payload, dict) and payload.get("skip") == "empty":
                        stats["empty_skipped"] += 1
                        if payload.get("url"):
                            skipped_details.append({"url": payload.get("url"), "reason": "empty"})
                        continue
                    rec = _build_record(
                        url_str=payload["url"],
                        clean_res=payload["clean_res"],
                        content_hash_raw=payload["content_hash"],
                        status_code=payload["status_code"],
                        final_url=payload["final_url"],
                        extractor_name=payload["extractor"],
                        display_title=payload["display_title"],
                        extractor_meta=payload.get("extractor_meta"),
                    )
                    if rec:
                        results.append(rec)
        if not results:
            if stats["dedup_skipped"] > 0 and stats["fetch_failed"] == 0:
                last_trigger_report.update({"stats": stats, "skipped_details": skipped_details})
                return []
            raise HTTPException(
                status_code=400,
                detail=(
                    "URL 抓取无有效内容，请检查地址/网络/解析规则。"
                    f"(dedup={stats['dedup_skipped']}, empty={stats['empty_skipped']}, failed={stats['fetch_failed']})"
                ),
            )

        last_trigger_report.update({"stats": stats, "skipped_details": skipped_details})
        return results

    def fetch_api() -> list[DataSourceContent]:
        api_mode = str(cfg.get("api_mode") or "http").strip() if isinstance(cfg, dict) else "http"

        if api_mode == "firecrawl_search":
            query = (cfg.get("query") if isinstance(cfg, dict) else "") or ""
            query = query.strip() if isinstance(query, str) else ""
            if not query:
                raise HTTPException(status_code=400, detail="FireCrawl 搜索模式需提供 query")

            firecrawl_api_key = (cfg.get("firecrawl_api_key") if isinstance(cfg, dict) else None) or ""
            firecrawl_api_base = cfg.get("firecrawl_api_base") if isinstance(cfg, dict) else None
            if not str(firecrawl_api_key).strip():
                picked = pick_api_key(db, "firecrawl", mark_used=True)
                if picked:
                    firecrawl_api_key = (picked.key or "").strip()
            if not str(firecrawl_api_key).strip():
                raise HTTPException(status_code=400, detail="FireCrawl 搜索模式未配置可用 API Key")

            sources = cfg.get("sources") if isinstance(cfg, dict) else None
            if not isinstance(sources, list) or not sources:
                sources = ["web"]
            limit_raw = cfg.get("limit", 10) if isinstance(cfg, dict) else 10
            try:
                limit = int(limit_raw)
            except Exception:
                limit = 10
            limit = max(1, min(100, limit))

            body: dict[str, Any] = {
                "query": query,
                "limit": limit,
                "sources": sources,
                "ignoreInvalidURLs": bool(cfg.get("ignore_invalid_urls", True)) if isinstance(cfg, dict) else True,
                "scrapeOptions": {
                    "formats": cfg.get("scrape_formats") if isinstance(cfg.get("scrape_formats"), list) else ["html"],
                },
            }
            tbs = cfg.get("tbs") if isinstance(cfg, dict) else None
            if isinstance(tbs, str) and tbs.strip():
                body["tbs"] = tbs.strip()

            base_v2 = _normalize_firecrawl_base(firecrawl_api_base)
            endpoint = base_v2.rstrip("/") + "/search"
            req_headers = {
                "Authorization": f"Bearer {firecrawl_api_key}",
                "Content-Type": "application/json",
            }
            try:
                resp = requests.post(endpoint, json=body, headers=req_headers, timeout=120)
                resp.raise_for_status()
                jd = resp.json()
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"FireCrawl 搜索失败：{exc}") from exc

            if not isinstance(jd, dict) or not jd.get("success"):
                raise HTTPException(status_code=400, detail=f"FireCrawl 搜索返回异常：{jd}")

            data = jd.get("data") or {}
            web_items: list[dict] = []
            if isinstance(data, dict):
                for src in sources:
                    arr = data.get(src)
                    if isinstance(arr, list):
                        for idx2, it in enumerate(arr):
                            if isinstance(it, dict):
                                it2 = dict(it)
                                it2["_firecrawl_source"] = src
                                it2["_firecrawl_rank"] = idx2 + 1
                                web_items.append(it2)

            parser_cfg = cfg.get("parser") if isinstance(cfg, dict) else None
            extractor_cfg = cfg.get("extractor") if isinstance(cfg, dict) else None
            cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None

            results: list[DataSourceContent] = []
            stats = {"dedup_skipped": 0, "empty_skipped": 0, "fetch_failed": 0}
            skipped_details: list[dict] = []
            for it in web_items:
                try:
                    url_str = it.get("url")
                    if not isinstance(url_str, str) or not url_str.strip():
                        continue
                    url_str = url_str.strip()

                    raw_html = it.get("html") or it.get("rawHtml") or it.get("markdown") or ""
                    if not isinstance(raw_html, str) or not raw_html.strip():
                        continue

                    extract_res = extract_main_text(raw_html, extractor_cfg if isinstance(extractor_cfg, dict) else None)
                    content_text = apply_parser(extract_res.main_text, parser_cfg)
                    if content_text == "":
                        stats["empty_skipped"] += 1
                        skipped_details.append({"url": url_str, "reason": "empty"})
                        continue

                    clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                    content_hash = hashlib.md5(content_text.encode("utf-8", "ignore")).hexdigest()

                    meta = it.get("metadata") if isinstance(it.get("metadata"), dict) else {}
                    status_code = meta.get("statusCode") if isinstance(meta, dict) else None
                    try:
                        status_code_int = int(status_code) if status_code is not None else None
                    except Exception:
                        status_code_int = None

                    url_hash = hashlib.md5(str(url_str).encode("utf-8", "ignore")).hexdigest()
                    last_rec = (
                        db.query(DataSourceContent)
                        .filter(
                            DataSourceContent.datasource_id == ds.id,
                            DataSourceContent.url_hash == url_hash,
                        )
                        .order_by(desc(DataSourceContent.fetched_at))
                        .first()
                    )
                    if (not force) and last_rec and isinstance(last_rec.extra, dict):
                        if (
                            last_rec.extra.get("content_hash_clean")
                            and last_rec.extra.get("content_hash_clean") == clean_res.content_hash_clean
                        ):
                            stats["dedup_skipped"] += 1
                            skipped_details.append(
                                {
                                    "url": str(url_str),
                                    "reason": "dedup_hash_clean_same",
                                    "matched_record_id": last_rec.id,
                                    "matched_fetched_at": last_rec.fetched_at.isoformat() if last_rec.fetched_at else None,
                                }
                            )
                            continue
                        if last_rec.extra.get("content_hash") == content_hash:
                            stats["dedup_skipped"] += 1
                            skipped_details.append(
                                {
                                    "url": str(url_str),
                                    "reason": "dedup_hash_raw_same",
                                    "matched_record_id": last_rec.id,
                                    "matched_fetched_at": last_rec.fetched_at.isoformat() if last_rec.fetched_at else None,
                                }
                            )
                            continue

                    display_title = it.get("title") if isinstance(it.get("title"), str) else None
                    rec = DataSourceContent(
                        datasource_id=ds.id,
                        source_type="url",
                        title=display_title or str(url_str),
                        url=str(url_str),
                        url_hash=url_hash,
                        content=clean_res.clean_text,
                        extra={
                            "status_code": status_code_int,
                            "final_url": meta.get("sourceURL") if isinstance(meta, dict) else None,
                            "firecrawl_mode": "search",
                            "firecrawl_query": query,
                            "firecrawl_source": it.get("_firecrawl_source"),
                            "firecrawl_rank": it.get("_firecrawl_rank"),
                            "firecrawl_title": display_title,
                            "firecrawl_description": it.get("description") or it.get("snippet"),
                            "extractor": extract_res.extractor,
                            "extractor_meta": extract_res.meta,
                            "content_hash": content_hash,
                            "content_hash_clean": clean_res.content_hash_clean,
                            "clean_stats": clean_res.stats,
                            "quality_flags": clean_res.quality_flags,
                        },
                        fetched_at=now_naive,
                    )
                    results.append(rec)
                except Exception:
                    stats["fetch_failed"] += 1
                    continue

            last_trigger_report.update({"stats": stats, "skipped_details": skipped_details})
            return results

        if api_mode == "aliyun_unified_search":
            query = (cfg.get("query") if isinstance(cfg, dict) else "") or ""
            query = query.strip() if isinstance(query, str) else ""
            if not query:
                raise HTTPException(status_code=400, detail="阿里统一搜索需提供 query")

            import os

            ak = (os.getenv("ALIYUN_ACCESS_KEY_ID") or os.getenv("ACCESS_KEY_ID") or "").strip()
            sk = (os.getenv("ALIYUN_ACCESS_KEY_SECRET") or os.getenv("ACCESS_KEY_SECRET") or "").strip()
            if not (ak and sk):
                picked = pick_api_key(db, "aliyun_iqs", mark_used=True)
                if picked and isinstance(getattr(picked, "extra", None), dict):
                    extra = picked.extra or {}
                    ak2 = str(extra.get("access_key_id") or extra.get("accessKeyId") or "").strip()
                    sk2 = str(extra.get("access_key_secret") or extra.get("accessKeySecret") or "").strip()
                    if ak2 and sk2:
                        ak, sk = ak2, sk2
            if not (ak and sk):
                raise HTTPException(status_code=400, detail="未配置阿里统一搜索 AK/SK")

            engine_type = str(cfg.get("engine_type") or "Generic").strip() or "Generic"
            time_range = str(cfg.get("time_range") or "NoLimit").strip() or "NoLimit"
            category = (str(cfg.get("category") or "").strip() or None) if isinstance(cfg, dict) else None
            location = (str(cfg.get("location") or "").strip() or None) if isinstance(cfg, dict) else None
            include_main_text = bool(cfg.get("include_main_text")) if isinstance(cfg, dict) and cfg.get("include_main_text") is not None else True
            advanced_params = cfg.get("advanced_params") if isinstance(cfg, dict) and isinstance(cfg.get("advanced_params"), dict) else None

            try:
                from alibabacloud_iqs20241111 import models
                from alibabacloud_iqs20241111.client import Client
                from alibabacloud_tea_openapi import models as open_api_models
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"阿里 SDK 未安装或导入失败：{exc}") from exc

            cfg_sdk = open_api_models.Config(access_key_id=ak, access_key_secret=sk)
            cfg_sdk.endpoint = "iqs.cn-zhangjiakou.aliyuncs.com"
            client = Client(cfg_sdk)

            contents = models.RequestContents(
                main_text=bool(include_main_text),
                markdown_text=False,
                summary=False,
                rerank_score=True,
                rich_main_body=False,
            )
            body = models.UnifiedSearchInput(
                query=query,
                time_range=time_range,
                engine_type=engine_type,
                category=category,
                location=location,
                contents=contents,
                advanced_params=advanced_params,
            )
            req = models.UnifiedSearchRequest(body=body)

            try:
                resp = client.unified_search(req)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"阿里统一搜索失败：{exc}") from exc

            page_items = getattr(resp.body, "page_items", None) or []
            parser_cfg = cfg.get("parser") if isinstance(cfg, dict) else None
            cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None

            results: list[DataSourceContent] = []
            stats = {"dedup_skipped": 0, "empty_skipped": 0, "fetch_failed": 0}
            skipped_details: list[dict] = []

            for idx2, it in enumerate(page_items):
                try:
                    link = getattr(it, "link", None)
                    if not isinstance(link, str) or not link.strip():
                        continue
                    url_str = link.strip()
                    title = getattr(it, "title", None)
                    title = title.strip() if isinstance(title, str) and title.strip() else None
                    snippet = getattr(it, "snippet", None)
                    snippet = snippet.strip() if isinstance(snippet, str) and snippet.strip() else None
                    main_text = getattr(it, "main_text", None)
                    main_text = main_text.strip() if isinstance(main_text, str) and main_text.strip() else None
                    published_time = getattr(it, "published_time", None)
                    rerank_score = getattr(it, "rerank_score", None)

                    raw_text = (main_text or "") or (snippet or "")
                    raw_text = raw_text.strip() if isinstance(raw_text, str) else ""
                    if not raw_text:
                        stats["empty_skipped"] += 1
                        skipped_details.append({"url": url_str, "reason": "empty"})
                        continue

                    parsed_text = apply_parser(raw_text, parser_cfg)
                    if parsed_text == "":
                        stats["empty_skipped"] += 1
                        skipped_details.append({"url": url_str, "reason": "empty"})
                        continue

                    clean_res = clean_text(parsed_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                    content_hash = hashlib.md5(parsed_text.encode("utf-8", "ignore")).hexdigest()

                    url_hash = hashlib.md5(str(url_str).encode("utf-8", "ignore")).hexdigest()
                    last_rec = (
                        db.query(DataSourceContent)
                        .filter(
                            DataSourceContent.datasource_id == ds.id,
                            DataSourceContent.url_hash == url_hash,
                        )
                        .order_by(desc(DataSourceContent.fetched_at))
                        .first()
                    )
                    if (not force) and last_rec and isinstance(last_rec.extra, dict):
                        if (
                            last_rec.extra.get("content_hash_clean")
                            and last_rec.extra.get("content_hash_clean") == clean_res.content_hash_clean
                        ):
                            stats["dedup_skipped"] += 1
                            continue
                        if last_rec.extra.get("content_hash") == content_hash:
                            stats["dedup_skipped"] += 1
                            continue

                    rec = DataSourceContent(
                        datasource_id=ds.id,
                        source_type="url",
                        title=title or str(url_str),
                        url=str(url_str),
                        url_hash=url_hash,
                        content=clean_res.clean_text,
                        extra={
                            "iqs_mode": "unified_search",
                            "iqs_query": query,
                            "iqs_engine_type": engine_type,
                            "iqs_time_range": time_range,
                            "iqs_category": category,
                            "iqs_location": location,
                            "iqs_rank": idx2 + 1,
                            "iqs_title": title,
                            "iqs_snippet": snippet,
                            "iqs_published_time": published_time,
                            "iqs_rerank_score": rerank_score,
                            "content_hash": content_hash,
                            "content_hash_clean": clean_res.content_hash_clean,
                            "clean_stats": clean_res.stats,
                            "quality_flags": clean_res.quality_flags,
                        },
                        fetched_at=now_naive,
                    )
                    results.append(rec)
                except Exception:
                    stats["fetch_failed"] += 1
                    continue

            last_trigger_report.update({"stats": stats, "skipped_details": skipped_details})
            return results

        api_url = cfg.get("api_url")
        if not api_url:
            raise HTTPException(status_code=400, detail="api 类型需提供 api_url")
        method = str(cfg.get("method") or "GET").upper()
        headers = cfg.get("headers") if isinstance(cfg, dict) else None
        params = cfg.get("params") if isinstance(cfg, dict) else None
        body = cfg.get("body") or cfg.get("data") if isinstance(cfg, dict) else None
        try:
            resp = requests.request(
                method,
                api_url,
                headers=headers,
                params=params,
                json=body if method != "GET" else None,
                timeout=20,
            )
            resp.raise_for_status()
            content_text = resp.text
        except RequestException as exc:
            raise HTTPException(status_code=400, detail=f"API 调用失败：{exc}") from exc

        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        clean_res = clean_text(
            content_text,
            cleaner_cfg if isinstance(cleaner_cfg, dict) else None,
        )
        return [
            DataSourceContent(
                datasource_id=ds.id,
                source_type="api",
                title=str(api_url),
                content=clean_res.clean_text,
                extra={
                    "status_code": resp.status_code,
                    "method": method,
                    "headers": headers,
                    "params": params,
                    "body": body,
                    "content_hash_clean": clean_res.content_hash_clean,
                    "clean_stats": clean_res.stats,
                    "quality_flags": clean_res.quality_flags,
                },
                fetched_at=now_naive,
            )
        ]

    def fetch_document() -> list[DataSourceContent]:
        doc_url = cfg.get("doc_url")
        if not doc_url:
            raise HTTPException(status_code=400, detail="document 类型需提供 doc_url")
        # 若已存在内容且未指定覆盖，则提示前端确认
        exists = (
            db.query(DataSourceContent)
            .filter(DataSourceContent.datasource_id == ds.id)
            .first()
        )
        if exists and not force:
            raise HTTPException(
                status_code=409, detail="文档内容已存在，如需覆盖请带上 force=true"
            )
        headers = cfg.get("headers") if isinstance(cfg, dict) else None
        try:
            resp = requests.get(doc_url, headers=headers, timeout=30)
            resp.raise_for_status()
            # 简单读取文本，二进制文件前端需提前转换为可读文本
            content_text = resp.text if resp.text else resp.content.decode("utf-8", "ignore")
        except RequestException as exc:
            raise HTTPException(status_code=400, detail=f"文档获取失败：{exc}") from exc

        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        clean_res = clean_text(
            content_text,
            cleaner_cfg if isinstance(cleaner_cfg, dict) else None,
        )
        return [
            DataSourceContent(
                datasource_id=ds.id,
                source_type="document",
                title=str(doc_url),
                content=clean_res.clean_text,
                extra={
                    "status_code": resp.status_code,
                    "content_type": resp.headers.get("Content-Type"),
                    "headers": headers,
                    "content_hash_clean": clean_res.content_hash_clean,
                    "clean_stats": clean_res.stats,
                    "quality_flags": clean_res.quality_flags,
                },
                fetched_at=now_naive,
            )
        ]

    def trigger_n8n() -> list[DataSourceContent]:
        webhook = None
        if isinstance(cfg, dict):
            webhook = cfg.get("n8n_webhook") or cfg.get("webhook")
        if not webhook:
            raise HTTPException(status_code=400, detail="n8n 类型需提供 webhook")
        payload = {
            "datasource_id": ds.id,
            "name": ds.name,
            "source_type": ds.source_type,
            "config": ds.config,
            "biz_category": ds.biz_category,
        }
        try:
            resp = requests.post(webhook, json=payload, timeout=15)
            resp.raise_for_status()
            content_text = resp.text or "n8n 触发成功"
        except RequestException as exc:
            raise HTTPException(status_code=400, detail=f"n8n 调用失败：{exc}") from exc

        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        clean_res = clean_text(
            content_text,
            cleaner_cfg if isinstance(cleaner_cfg, dict) else None,
        )
        return [
            DataSourceContent(
                datasource_id=ds.id,
                source_type="n8n",
                title=str(webhook),
                content=clean_res.clean_text,
                extra={
                    "status_code": resp.status_code,
                    "webhook": webhook,
                    "content_hash_clean": clean_res.content_hash_clean,
                    "clean_stats": clean_res.stats,
                    "quality_flags": clean_res.quality_flags,
                },
                fetched_at=now_naive,
            )
        ]

    # 按类型获取内容
    contents: list[DataSourceContent] = []
    if ds.source_type == "url":
        contents = fetch_urls()
    elif ds.source_type == "api":
        contents = fetch_api()
    elif ds.source_type == "document":
        contents = fetch_document()
    elif ds.source_type == "n8n":
        contents = trigger_n8n()
    else:
        raise HTTPException(status_code=400, detail="不支持的数据源类型")

    ds.last_run_at = now_naive
    ds.next_run_at = (
        compute_next_run(ds.schedule_cron, now_local)
        if ds.schedule_cron and ds.enable_schedule
        else None
    )

    # 中文说明：把本次触发的统计信息写回 config，便于前端查看/排障。
    # 注意：SQLAlchemy 的 JSON 字段默认不追踪 dict 原地修改，这里必须拷贝并标记修改。
    cfg2 = dict(ds.config) if isinstance(ds.config, dict) else {}
    report_stats = last_trigger_report.get("stats") if isinstance(last_trigger_report, dict) else None
    report_skipped = last_trigger_report.get("skipped_details") if isinstance(last_trigger_report, dict) else None
    cfg2["_last_trigger"] = {
        "triggered_at": now_naive.isoformat(),
        "force": bool(force),
        "ingested": len(contents) if isinstance(contents, list) else 0,
        "stats": report_stats,
        # 控制体积，最多保存 50 条跳过明细
        "skipped_details": (report_skipped[:50] if isinstance(report_skipped, list) else []),
    }
    ds.config = cfg2
    flag_modified(ds, "config")

    for item in contents:
        db.add(item)
    db.commit()
    db.refresh(ds)

    return ds
