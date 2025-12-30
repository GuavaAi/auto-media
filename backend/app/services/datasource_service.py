"""
数据源抓取业务逻辑服务
将原 datasource.py 中的抓取逻辑抽离到此处
"""
from datetime import datetime, timedelta
from typing import Any, Optional
import hashlib
import concurrent.futures
import logging

import requests
from requests import RequestException
from sqlalchemy.orm import Session

from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent
from app.models.user import User
from app.services.crawler import (
    get_crawler_by_engine,
    apply_parser,
    discover_links,
)
from app.services.api_key_pool import pick_api_key
from app.services.text_cleaner import clean_text
from app.services.readability_extractor import extract_main_text
from app.factories.content_factory import ContentFactory, compute_url_hash, compute_content_hash
from app.repositories.datasource_repo import DataSourceRepository, DataSourceContentRepository

logger = logging.getLogger(__name__)


def _normalize_firecrawl_base(base: str | None) -> str:
    """标准化 FireCrawl API 基础 URL"""
    b = (base or "https://api.firecrawl.dev/v1").rstrip("/")
    if b.endswith("/v2"):
        return b
    if b.endswith("/v2/search"):
        return b[: -len("/search")]
    if b.endswith("/v1"):
        return b[: -len("/v1")] + "/v2"
    return b + "/v2"


def _compute_next_run(cron_expr: str | None, start_dt: datetime) -> datetime | None:
    """根据 cron 表达式计算下次运行时间"""
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


class FetchStats:
    """抓取统计信息"""

    def __init__(self):
        self.dedup_skipped = 0
        self.empty_skipped = 0
        self.fetch_failed = 0
        self.skipped_details: list[dict] = []

    def to_dict(self) -> dict:
        return {
            "dedup_skipped": self.dedup_skipped,
            "empty_skipped": self.empty_skipped,
            "fetch_failed": self.fetch_failed,
        }

    def add_skipped(self, url: str, reason: str, matched_record: Optional[DataSourceContent] = None):
        detail = {"url": url, "reason": reason}
        if matched_record:
            detail["matched_record_id"] = matched_record.id
            detail["matched_fetched_at"] = (
                matched_record.fetched_at.isoformat() if matched_record.fetched_at else None
            )
        self.skipped_details.append(detail)


class DataSourceService:
    """数据源抓取服务"""

    def __init__(self, db: Session):
        self.db = db
        self.ds_repo = DataSourceRepository(db)
        self.content_repo = DataSourceContentRepository(db)

    def run_datasource(
        self,
        ds: DataSource,
        force: bool = False,
        current_user: Optional[User] = None,
    ) -> DataSource:
        """
        执行单个数据源的抓取逻辑，更新 last_run_at / next_run_at / _last_trigger 报告
        """
        now_local = datetime.now()
        now_naive = now_local
        cfg = ds.config if isinstance(ds.config, dict) else {}

        # 中文说明：抓取记录（DataSourceContent）的 user_id 以数据源归属为准。
        # - 定时任务触发：current_user=None，此时应与 ds.user_id 保持一致
        # - 若历史数据源未设置 user_id，但存在 current_user（手动触发），则回退到 current_user.id
        record_user_id = getattr(ds, "user_id", None)
        if record_user_id is None and current_user is not None:
            record_user_id = getattr(current_user, "id", None)

        # 用于统计本次触发的信息
        stats = FetchStats()

        # 按类型获取内容
        contents: list[DataSourceContent] = []
        if ds.source_type == "url":
            contents = self._fetch_urls(ds, cfg, now_naive, force, stats, record_user_id)
        elif ds.source_type == "api":
            contents = self._fetch_api(ds, cfg, now_naive, force, stats, record_user_id)
        elif ds.source_type == "document":
            contents = self._fetch_document(ds, cfg, now_naive, force, record_user_id)
        elif ds.source_type == "n8n":
            contents = self._trigger_n8n(ds, cfg, now_naive, record_user_id)
        else:
            raise ValueError("不支持的数据源类型")

        # 更新运行时间
        self.ds_repo.update_run_times(
            ds,
            last_run_at=now_naive,
            next_run_at=_compute_next_run(ds.schedule_cron, now_local) if ds.schedule_cron and ds.enable_schedule else None,
        )

        # 更新配置中的触发报告
        trigger_report = {"stats": stats.to_dict(), "skipped_details": stats.skipped_details}
        self.ds_repo.update_config_with_trigger_report(ds, trigger_report, len(contents), force)

        # 保存内容
        self.content_repo.add_batch(contents)
        self.content_repo.commit()
        self.db.refresh(ds)

        return ds

    def _fetch_urls(
        self,
        ds: DataSource,
        cfg: dict,
        now_naive: datetime,
        force: bool,
        stats: FetchStats,
        record_user_id: int | None,
    ) -> list[DataSourceContent]:
        """URL 类型抓取"""
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
        crawl4ai_options = cfg.get("crawl4ai_options") if isinstance(cfg, dict) else None
        extractor_cfg = cfg.get("extractor") if isinstance(cfg, dict) else None
        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        sub_concurrency = int(cfg.get("sub_concurrency", 12) or 12) if isinstance(cfg, dict) else 12
        engine_lower = crawler_engine.lower()

        if not urls or not isinstance(urls, list):
            raise ValueError("url 类型需提供 urls 列表")

        # 子页面过滤：只支持 css_selector
        sub_parser_cfg = None
        if isinstance(sub_parser_cfg_raw, dict):
            css = sub_parser_cfg_raw.get("css_selector")
            if isinstance(css, str) and css.strip():
                sub_parser_cfg = {"css_selector": css.strip()}
        if sub_parser_cfg is None and isinstance(parser_cfg, dict):
            css = parser_cfg.get("css_selector")
            if isinstance(css, str) and css.strip():
                sub_parser_cfg = {"css_selector": css.strip()}

        # Firecrawl batch 不支持动态发现子页面
        use_firecrawl_batch = (
            engine_lower == "firecrawl"
            and isinstance(firecrawl_batch, dict)
            and bool(firecrawl_batch.get("enabled"))
        )
        if use_firecrawl_batch:
            auto_discover = False

        # 构建抓取队列
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
        discovered_subpages: list[str] = []
        discovered_seen: set[str] = set()

        # 中文说明：父页面按“当天”控制只抓一次（跨天保留）。
        # 这里用 now_naive 的日期作为“当天”口径。
        day_start = now_naive.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        if engine_lower == "firecrawl" and not (firecrawl_api_key or "").strip():
            picked = pick_api_key(self.db, "firecrawl", mark_used=True)
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

        def _extract_text_from_html(html: str, url: str) -> tuple[str, str | None, dict | None]:
            # 中文说明：若配置了 css_selector，则必须在原始 HTML 上做选择器抽取。
            # 否则 readability/bs4 抽取后会变成纯文本，css_selector 将无法生效。
            if isinstance(parser_cfg, dict) and parser_cfg.get("css_selector"):
                content_text = apply_parser(html, parser_cfg)
                return content_text, "css_selector", None
            extract_res = extract_main_text(html, extractor_cfg if isinstance(extractor_cfg, dict) else None)
            content_text = apply_parser(extract_res.main_text, parser_cfg)
            return content_text, extract_res.extractor, extract_res.meta if isinstance(extract_res.meta, dict) else None

        def _extract_text_from_subpage_html(html: str, url: str) -> tuple[str, str | None, dict | None]:
            # 中文说明：子页面同理，优先在原始 HTML 上应用 sub_parser.css_selector。
            if isinstance(sub_parser_cfg, dict) and sub_parser_cfg.get("css_selector"):
                content_text = apply_parser(html, sub_parser_cfg)
                return content_text, "css_selector", None
            extract_res = extract_main_text(html, extractor_cfg if isinstance(extractor_cfg, dict) else None)
            content_text = apply_parser(extract_res.main_text, sub_parser_cfg)
            return content_text, extract_res.extractor, extract_res.meta if isinstance(extract_res.meta, dict) else None

        def _build_record(
            *,
            url_str: str,
            clean_res: Any,
            content_hash_raw: str,
            status_code: int | None,
            final_url: str | None,
            extractor_name: str | None,
            display_title: str | None,
            extractor_meta: dict | None,
            is_discovered: bool = False,
        ) -> DataSourceContent | None:
            url_hash = compute_url_hash(url_str)
            should_skip, matched = self.content_repo.check_dedup(
                ds.id, url_hash, content_hash_raw,
                getattr(clean_res, "content_hash_clean", None), force
            )
            if should_skip:
                stats.dedup_skipped += 1
                reason = "dedup_hash_clean_same" if matched and matched.extra.get("content_hash_clean") else "dedup_hash_raw_same"
                stats.add_skipped(url_str, reason, matched)
                return None

            return ContentFactory.create_url_content(
                user_id=record_user_id,
                datasource_id=ds.id,
                url=url_str,
                title=display_title,
                content=getattr(clean_res, "clean_text", "") or "",
                status_code=status_code,
                final_url=final_url,
                is_discovered=is_discovered,
                extractor=extractor_name,
                extractor_meta=extractor_meta,
                content_hash=content_hash_raw,
                content_hash_clean=getattr(clean_res, "content_hash_clean", None),
                clean_stats=getattr(clean_res, "stats", None),
                quality_flags=getattr(clean_res, "quality_flags", None),
                fetched_at=now_naive,
            )

        def _fetch_subpage(url: str) -> dict | None:
            try:
                page = crawler.fetch(url, headers=headers)
                html = page.html or ""
                if not isinstance(html, str) or not html.strip():
                    return {"skip": "empty", "url": url}
                content_text, extractor_name, extractor_meta = _extract_text_from_subpage_html(html, url)
                if content_text == "":
                    return {"skip": "empty", "url": url}
                clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                content_hash = compute_content_hash(content_text)
                return {
                    "url": url,
                    "clean_res": clean_res,
                    "content_hash": content_hash,
                    "status_code": getattr(page, "status_code", None),
                    "final_url": getattr(page, "final_url", None),
                    "extractor": extractor_name,
                    "display_title": None,
                    "extractor_meta": extractor_meta,
                }
            except Exception:
                return None

        while idx < len(full_urls):
            url, is_discovered = full_urls[idx]
            idx += 1

            # 中文说明：子页面统一走并发抓取（sub_parser），避免在主循环抓取一次后又在并发阶段重复抓取。
            if is_discovered:
                u = str(url)
                if u and u not in discovered_seen:
                    discovered_subpages.append(u)
                    discovered_seen.add(u)
                continue

            # 中文说明：父页面同一天只抓一次。force=true 时允许覆盖当天记录。
            url_str = str(url)
            url_hash = compute_url_hash(url_str)
            parent_today = self.content_repo.get_parent_record_for_day(
                ds.id, url_hash, day_start, day_end
            )
            if parent_today and not force:
                stats.dedup_skipped += 1
                stats.add_skipped(url_str, "parent_daily_dedup", parent_today)
                continue

            try:
                page = crawler.fetch(url, headers=headers)
                html = page.html or ""
                if not isinstance(html, str) or not html.strip():
                    stats.empty_skipped += 1
                    stats.add_skipped(str(url), "empty")
                    continue

                content_text, extractor_name, extractor_meta = _extract_text_from_html(html, url)
                if content_text == "":
                    stats.empty_skipped += 1
                    stats.add_skipped(str(url), "empty")
                    continue

                clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                content_hash = compute_content_hash(content_text)

                # 中文说明：force=true 且当天已有父页面记录，则覆盖更新，不新增。
                if parent_today and force:
                    if parent_today.user_id != record_user_id:
                        parent_today.user_id = record_user_id
                    overwrite_extra = {
                        "status_code": getattr(page, "status_code", None),
                        "final_url": getattr(page, "final_url", None),
                        "is_discovered": False,
                        "extractor": extractor_name,
                        "extractor_meta": extractor_meta,
                        "content_hash": content_hash,
                        "content_hash_clean": getattr(clean_res, "content_hash_clean", None),
                        "clean_stats": getattr(clean_res, "stats", None),
                        "quality_flags": getattr(clean_res, "quality_flags", None),
                    }
                    self.content_repo.update_record(
                        parent_today,
                        title=None,
                        content=getattr(clean_res, "clean_text", "") or "",
                        extra=overwrite_extra,
                        fetched_at=now_naive,
                    )
                    results.append(parent_today)
                    # 覆盖场景下，不再自动发现子页面（避免一次手动覆盖触发大量子页面抓取）
                    continue

                rec = _build_record(
                    url_str=str(url),
                    clean_res=clean_res,
                    content_hash_raw=content_hash,
                    status_code=getattr(page, "status_code", None),
                    final_url=getattr(page, "final_url", None),
                    extractor_name=extractor_name,
                    display_title=None,
                    extractor_meta=extractor_meta,
                    is_discovered=is_discovered,
                )
                if rec:
                    results.append(rec)
            except Exception as exc:
                logger.error(f"Fetch failed for {url}: {str(exc)}")
                stats.fetch_failed += 1
                continue

            # 自动发现子页面
            if auto_discover and discover_budget > 0:
                try:
                    discovered_links = discover_links(html, url, discover_budget, seen, parser_cfg)
                except Exception:
                    discovered_links = []
                for link in discovered_links:
                    if link not in seen and discover_budget > 0:
                        full_urls.append((link, True))
                        seen.add(link)
                        discover_budget -= 1

        # 子页面并发抓取
        subpage_urls = discovered_subpages
        if isinstance(sub_parser_cfg, dict) and subpage_urls:
            workers = max(1, min(32, sub_concurrency))
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(_fetch_subpage, u) for u in subpage_urls]
                for fut in concurrent.futures.as_completed(futs):
                    try:
                        payload = fut.result()
                    except Exception:
                        stats.fetch_failed += 1
                        continue
                    if not payload:
                        continue
                    if isinstance(payload, dict) and payload.get("skip") == "empty":
                        stats.empty_skipped += 1
                        if payload.get("url"):
                            stats.add_skipped(payload.get("url"), "empty")
                        continue
                    rec2 = _build_record(
                        url_str=payload["url"],
                        clean_res=payload["clean_res"],
                        content_hash_raw=payload["content_hash"],
                        status_code=payload.get("status_code"),
                        final_url=payload.get("final_url"),
                        extractor_name=payload.get("extractor"),
                        display_title=payload.get("display_title"),
                        extractor_meta=payload.get("extractor_meta"),
                        is_discovered=True,
                    )
                    if rec2:
                        results.append(rec2)

        return results

    def _fetch_api(
        self,
        ds: DataSource,
        cfg: dict,
        now_naive: datetime,
        force: bool,
        stats: FetchStats,
        record_user_id: int | None,
    ) -> list[DataSourceContent]:
        """API 类型抓取"""
        api_mode = str(cfg.get("api_mode") or "http").strip() if isinstance(cfg, dict) else "http"

        if api_mode == "firecrawl_search":
            return self._fetch_firecrawl_search(ds, cfg, now_naive, force, stats, record_user_id)

        if api_mode == "aliyun_unified_search":
            return self._fetch_aliyun_iqs(ds, cfg, now_naive, force, stats, record_user_id)

        # 普通 HTTP API
        api_url = cfg.get("api_url")
        if not api_url:
            raise ValueError("api 类型需提供 api_url")
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
            raise ValueError(f"API 调用失败：{exc}") from exc

        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)

        return [
            ContentFactory.create_api_content(
                user_id=record_user_id,
                datasource_id=ds.id,
                api_url=str(api_url),
                content=clean_res.clean_text,
                status_code=resp.status_code,
                method=method,
                headers=headers,
                params=params,
                body=body,
                content_hash_clean=clean_res.content_hash_clean,
                clean_stats=clean_res.stats,
                quality_flags=clean_res.quality_flags,
                fetched_at=now_naive,
            )
        ]

    def _fetch_firecrawl_search(
        self,
        ds: DataSource,
        cfg: dict,
        now_naive: datetime,
        force: bool,
        stats: FetchStats,
        record_user_id: int | None,
    ) -> list[DataSourceContent]:
        """FireCrawl 搜索模式"""
        query = (cfg.get("query") if isinstance(cfg, dict) else "") or ""
        query = query.strip() if isinstance(query, str) else ""
        if not query:
            raise ValueError("FireCrawl 搜索模式需提供 query")

        firecrawl_api_key = (cfg.get("firecrawl_api_key") if isinstance(cfg, dict) else None) or ""
        firecrawl_api_base = cfg.get("firecrawl_api_base") if isinstance(cfg, dict) else None
        if not str(firecrawl_api_key).strip():
            picked = pick_api_key(self.db, "firecrawl", mark_used=True)
            if picked:
                firecrawl_api_key = (picked.key or "").strip()
        if not str(firecrawl_api_key).strip():
            raise ValueError("FireCrawl 搜索模式未配置可用 API Key")

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
            raise ValueError(f"FireCrawl 搜索失败：{exc}") from exc

        if not isinstance(jd, dict) or not jd.get("success"):
            raise ValueError(f"FireCrawl 搜索返回异常：{jd}")

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
                    stats.empty_skipped += 1
                    stats.add_skipped(url_str, "empty")
                    continue

                clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                content_hash = compute_content_hash(content_text)

                meta = it.get("metadata") if isinstance(it.get("metadata"), dict) else {}
                status_code = meta.get("statusCode") if isinstance(meta, dict) else None
                try:
                    status_code_int = int(status_code) if status_code is not None else None
                except Exception:
                    status_code_int = None

                url_hash = compute_url_hash(url_str)
                should_skip, matched = self.content_repo.check_dedup(
                    ds.id, url_hash, content_hash, clean_res.content_hash_clean, force
                )
                if should_skip:
                    stats.dedup_skipped += 1
                    reason = "dedup_hash_clean_same" if matched and matched.extra.get("content_hash_clean") else "dedup_hash_raw_same"
                    stats.add_skipped(url_str, reason, matched)
                    continue

                display_title = it.get("title") if isinstance(it.get("title"), str) else None
                rec = ContentFactory.create_firecrawl_search_content(
                    user_id=record_user_id,
                    datasource_id=ds.id,
                    url=url_str,
                    title=display_title,
                    content=clean_res.clean_text,
                    query=query,
                    status_code=status_code_int,
                    final_url=meta.get("sourceURL") if isinstance(meta, dict) else None,
                    firecrawl_source=it.get("_firecrawl_source"),
                    firecrawl_rank=it.get("_firecrawl_rank"),
                    firecrawl_description=it.get("description") or it.get("snippet"),
                    extractor=extract_res.extractor,
                    extractor_meta=extract_res.meta,
                    content_hash=content_hash,
                    content_hash_clean=clean_res.content_hash_clean,
                    clean_stats=clean_res.stats,
                    quality_flags=clean_res.quality_flags,
                    fetched_at=now_naive,
                )
                results.append(rec)
            except Exception:
                stats.fetch_failed += 1
                continue

        return results

    def _fetch_aliyun_iqs(
        self,
        ds: DataSource,
        cfg: dict,
        now_naive: datetime,
        force: bool,
        stats: FetchStats,
        record_user_id: int | None,
    ) -> list[DataSourceContent]:
        """阿里统一搜索模式"""
        import os

        query = (cfg.get("query") if isinstance(cfg, dict) else "") or ""
        query = query.strip() if isinstance(query, str) else ""
        if not query:
            raise ValueError("阿里统一搜索需提供 query")

        ak = (os.getenv("ALIYUN_ACCESS_KEY_ID") or os.getenv("ACCESS_KEY_ID") or "").strip()
        sk = (os.getenv("ALIYUN_ACCESS_KEY_SECRET") or os.getenv("ACCESS_KEY_SECRET") or "").strip()
        if not (ak and sk):
            picked = pick_api_key(self.db, "aliyun_iqs", mark_used=True)
            if picked and isinstance(getattr(picked, "extra", None), dict):
                extra = picked.extra or {}
                ak2 = str(extra.get("access_key_id") or extra.get("accessKeyId") or "").strip()
                sk2 = str(extra.get("access_key_secret") or extra.get("accessKeySecret") or "").strip()
                if ak2 and sk2:
                    ak, sk = ak2, sk2
        if not (ak and sk):
            raise ValueError("未配置阿里统一搜索 AK/SK")

        engine_type = str(cfg.get("engine_type") or "Generic").strip() or "Generic"
        time_range = str(cfg.get("time_range") or "NoLimit").strip() or "NoLimit"
        category = (str(cfg.get("category") or "").strip() or None) if isinstance(cfg, dict) else None
        location = (str(cfg.get("location") or "").strip() or None) if isinstance(cfg, dict) else None
        include_main_text = (
            bool(cfg.get("include_main_text"))
            if isinstance(cfg, dict) and cfg.get("include_main_text") is not None
            else True
        )
        advanced_params = (
            cfg.get("advanced_params")
            if isinstance(cfg, dict) and isinstance(cfg.get("advanced_params"), dict)
            else None
        )

        try:
            from alibabacloud_iqs20241111 import models
            from alibabacloud_iqs20241111.client import Client
            from alibabacloud_tea_openapi import models as open_api_models
        except Exception as exc:
            raise ValueError(f"阿里 SDK 未安装或导入失败：{exc}") from exc

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
            raise ValueError(f"阿里统一搜索失败：{exc}") from exc

        page_items = getattr(resp.body, "page_items", None) or []
        parser_cfg = cfg.get("parser") if isinstance(cfg, dict) else None
        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None

        results: list[DataSourceContent] = []
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
                    stats.empty_skipped += 1
                    stats.add_skipped(url_str, "empty")
                    continue

                parsed_text = apply_parser(raw_text, parser_cfg)
                if parsed_text == "":
                    stats.empty_skipped += 1
                    stats.add_skipped(url_str, "empty")
                    continue

                clean_res = clean_text(parsed_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)
                content_hash = compute_content_hash(parsed_text)

                url_hash = compute_url_hash(url_str)
                should_skip, matched = self.content_repo.check_dedup(
                    ds.id, url_hash, content_hash, clean_res.content_hash_clean, force
                )
                if should_skip:
                    stats.dedup_skipped += 1
                    continue

                rec = ContentFactory.create_aliyun_iqs_content(
                    user_id=record_user_id,
                    datasource_id=ds.id,
                    url=url_str,
                    title=title,
                    content=clean_res.clean_text,
                    query=query,
                    engine_type=engine_type,
                    time_range=time_range,
                    category=category,
                    location=location,
                    rank=idx2 + 1,
                    snippet=snippet,
                    published_time=published_time,
                    rerank_score=rerank_score,
                    content_hash=content_hash,
                    content_hash_clean=clean_res.content_hash_clean,
                    clean_stats=clean_res.stats,
                    quality_flags=clean_res.quality_flags,
                    fetched_at=now_naive,
                )
                results.append(rec)
            except Exception:
                stats.fetch_failed += 1
                continue

        return results

    def _fetch_document(
        self,
        ds: DataSource,
        cfg: dict,
        now_naive: datetime,
        force: bool,
        record_user_id: int | None,
    ) -> list[DataSourceContent]:
        """文档类型抓取"""
        doc_url = cfg.get("doc_url")
        if not doc_url:
            raise ValueError("document 类型需提供 doc_url")

        # 若已存在内容且未指定覆盖，则提示确认
        if self.content_repo.exists_by_datasource_id(ds.id) and not force:
            raise ValueError("文档内容已存在，如需覆盖请带上 force=true")

        headers = cfg.get("headers") if isinstance(cfg, dict) else None
        try:
            resp = requests.get(doc_url, headers=headers, timeout=30)
            resp.raise_for_status()
            content_text = resp.text if resp.text else resp.content.decode("utf-8", "ignore")
        except RequestException as exc:
            raise ValueError(f"文档获取失败：{exc}") from exc

        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)

        return [
            ContentFactory.create_document_content(
                user_id=record_user_id,
                datasource_id=ds.id,
                doc_url=str(doc_url),
                content=clean_res.clean_text,
                status_code=resp.status_code,
                content_type=resp.headers.get("Content-Type"),
                headers=headers,
                content_hash_clean=clean_res.content_hash_clean,
                clean_stats=clean_res.stats,
                quality_flags=clean_res.quality_flags,
                fetched_at=now_naive,
            )
        ]

    def _trigger_n8n(
        self,
        ds: DataSource,
        cfg: dict,
        now_naive: datetime,
        record_user_id: int | None,
    ) -> list[DataSourceContent]:
        """n8n webhook 触发"""
        webhook = None
        if isinstance(cfg, dict):
            webhook = cfg.get("n8n_webhook") or cfg.get("webhook")
        if not webhook:
            raise ValueError("n8n 类型需提供 webhook")

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
            raise ValueError(f"n8n 调用失败：{exc}") from exc

        cleaner_cfg = cfg.get("cleaner") if isinstance(cfg, dict) else None
        clean_res = clean_text(content_text, cleaner_cfg if isinstance(cleaner_cfg, dict) else None)

        return [
            ContentFactory.create_n8n_content(
                user_id=record_user_id,
                datasource_id=ds.id,
                webhook=str(webhook),
                content=clean_res.clean_text,
                status_code=resp.status_code,
                content_hash_clean=clean_res.content_hash_clean,
                clean_stats=clean_res.stats,
                quality_flags=clean_res.quality_flags,
                fetched_at=now_naive,
            )
        ]
