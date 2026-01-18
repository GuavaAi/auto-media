from __future__ import annotations

import hashlib
from datetime import datetime
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

import requests

from app import deps
from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent
from app.models.material_pack import MaterialPack
from app.models.material_item import MaterialItem
from app.models.user import User
from app.schemas.material import (
    AliyunUnifiedSearchIngestRequest,
    AliyunUnifiedSearchIngestResponse,
    DedupeResponse,
    FirecrawlSearchIngestRequest,
    FirecrawlSearchIngestResponse,
    SerpapiSearchIngestRequest,
    SerpapiSearchIngestResponse,
    MaterialItemBatchCreateRequest,
    MaterialItemOut,
    MaterialItemSearchResponse,
    MaterialItemUpdate,
    MaterialPackCreate,
    MaterialPackDetailResponse,
    MaterialPackListResponse,
    MaterialPackOut,
)
from app.services.api_key_pool import pick_api_key
from app.services.user_service import is_admin

router = APIRouter()


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split())


def _hash_item(item_type: str, text: str) -> str:
    raw = f"{(item_type or '').strip().lower()}|{_norm_text(text)}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _preview_text(text: str, max_len: int = 220) -> str:
    t = (text or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    if len(t) <= max_len:
        return t
    return t[:max_len] + "..."


def _build_cached_item(rec: DataSourceContent, title: str | None, meta: dict | None = None) -> dict:
    """中文说明：命中去重时，将历史内容回填给前端展示。"""
    display_title = (title or rec.title or rec.url or "").strip() or (rec.url or "")
    return {
        "item_type": "source",
        "text": f"{display_title}\n{rec.content or ''}",
        "source_url": rec.url,
        "source_content_id": rec.id,
        "meta": meta or {},
    }


def _serpapi_search(
    *,
    api_key: str,
    query: str,
    engine: str,
    limit: int,
    tbs: str | None,
    hl: str | None,
    gl: str | None,
    location: str | None,
) -> dict[str, Any]:
    # 中文说明：SerpAPI 使用 HTTP 调用，统一走 search.json。
    endpoint = "https://serpapi.com/search.json"
    params: dict[str, Any] = {
        "api_key": api_key,
        "engine": engine,
        "q": query,
        "num": max(1, min(100, int(limit or 10))),
    }
    if tbs:
        params["tbs"] = tbs
    if hl:
        params["hl"] = hl
    if gl:
        params["gl"] = gl
    if location:
        params["location"] = location

    try:
        resp = requests.get(endpoint, params=params, timeout=30)
    except Exception as exc:
        raise RuntimeError(f"SerpAPI 请求失败：{exc}") from exc

    if resp.status_code >= 400:
        raise RuntimeError(f"SerpAPI 请求失败（HTTP {resp.status_code}）：{_safe_resp_text(resp)}")

    try:
        return resp.json()
    except Exception as exc:
        raise RuntimeError(f"SerpAPI 返回非 JSON：{_safe_resp_text(resp)}") from exc


def _normalize_firecrawl_base(base: str | None) -> str:
    b = (base or "https://api.firecrawl.dev/v1").rstrip("/")
    if b.endswith("/v2"):
        return b
    if b.endswith("/v2/search"):
        return b[: -len("/search")]
    if b.endswith("/v1"):
        return b[: -len("/v1")] + "/v2"
    return b + "/v2"


def _resolve_aliyun_iqs_apikey_endpoint(extra: dict | None = None) -> str:
    # 中文说明：APIKey(Bearer) 模式统一使用 cloud-iqs 的公共入口；允许通过环境变量或 extra 覆盖。
    env_ep = (os.getenv("ALIYUN_IQS_API_ENDPOINT") or "").strip()
    if env_ep:
        return env_ep
    if isinstance(extra, dict):
        ep2 = str(extra.get("api_endpoint") or extra.get("endpoint") or "").strip()
        if ep2:
            return ep2
    return "https://cloud-iqs.aliyuncs.com/search/unified"


def _safe_resp_text(resp: requests.Response, max_len: int = 1200) -> str:
    # 中文说明：响应体可能很长，这里截断输出用于排障；避免泄露敏感信息。
    try:
        t = resp.text or ""
    except Exception:
        t = ""
    t = t.strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    return t[:max_len] + "..."


def _resolve_aliyun_iqs_credentials(db: Session) -> dict[str, Any]:
    """解析阿里统一搜索调用凭证。

    优先级：
    1) AK/SK（SDK 调用）：环境变量 ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET
    2) AK/SK（SDK 调用）：API Key 池 provider=aliyun_iqs 的 extra.access_key_id/access_key_secret
    """

    ak = (os.getenv("ALIYUN_ACCESS_KEY_ID") or os.getenv("ACCESS_KEY_ID") or "").strip()
    sk = (os.getenv("ALIYUN_ACCESS_KEY_SECRET") or os.getenv("ACCESS_KEY_SECRET") or "").strip()
    if ak and sk:
        return {"mode": "aksk", "access_key_id": ak, "access_key_secret": sk}

    picked = pick_api_key(db, "aliyun_iqs", mark_used=True)
    if picked:
        if isinstance(getattr(picked, "extra", None), dict):
            extra = picked.extra or {}
            ak2 = str(extra.get("access_key_id") or extra.get("accessKeyId") or "").strip()
            sk2 = str(extra.get("access_key_secret") or extra.get("accessKeySecret") or "").strip()
            if ak2 and sk2:
                return {"mode": "aksk", "access_key_id": ak2, "access_key_secret": sk2}

        # 如果没有配置 AK/SK，但配置了 key，则使用 API Key 模式
        if picked.key and str(picked.key).strip():
            extra2 = picked.extra if isinstance(getattr(picked, "extra", None), dict) else None
            return {
                "mode": "apikey",
                "api_key": str(picked.key).strip(),
                "api_endpoint": _resolve_aliyun_iqs_apikey_endpoint(extra2),
            }

    raise HTTPException(
        status_code=400,
        detail=(
            "未配置阿里统一搜索凭证。请配置环境变量 ALIYUN_ACCESS_KEY_ID/SECRET (SDK模式)，"
            "或在 APIKey 池配置 aliyun_iqs (支持 extra.access_key_id/secret 或直接 key)"
        ),
    )



def _aliyun_iqs_call_via_apikey(
    *,
    query: str,
    engine_type: str,
    time_range: str,
    category: str | None,
    location: str | None,
    include_main_text: bool,
    advanced_params: dict[str, str] | None,
    api_key: str,
    endpoint: str,
) -> dict[str, Any]:
    """通过 HTTP API (Bearer Token) 调用阿里云统一搜索"""
    ep = (endpoint or "").strip() or "https://cloud-iqs.aliyuncs.com/search/unified"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # API 参数构造，参考 SDK 模型与通用 API 规范 (camelCase)
    body = {
        "query": query,
        "engineType": engine_type,
        "timeRange": time_range,
        "contents": {
            "mainText": include_main_text,
            "markdownText": False,
            "summary": False,
            "rerankScore": True,
        },
    }
    if category:
        body["category"] = category
    if location:
        body["location"] = location
    if advanced_params:
        body["advancedParams"] = advanced_params

    try:
        resp = requests.post(ep, json=body, headers=headers, timeout=30)
    except Exception as exc:
        raise RuntimeError(f"API Key 调用失败（请求异常，endpoint={ep}）：{exc}") from exc

    if resp.status_code >= 400:
        detail = _safe_resp_text(resp)
        raise RuntimeError(f"API Key 调用失败（HTTP {resp.status_code}，endpoint={ep}）：{detail}")

    try:
        data = resp.json()
    except Exception as exc:
        detail = _safe_resp_text(resp)
        raise RuntimeError(f"API Key 调用失败（非 JSON 响应，endpoint={ep}）：{detail}") from exc
    
    # 兼容返回结构
    if "pageItems" not in data and "result" in data and isinstance(data["result"], dict):
         data = data["result"]
         
    return data


def _aliyun_iqs_call_via_sdk(*, query: str, engine_type: str, time_range: str, category: str | None, location: str | None, include_main_text: bool, advanced_params: dict[str, str] | None, access_key_id: str, access_key_secret: str) -> dict[str, Any]:
    try:
        from alibabacloud_iqs20241111 import models
        from alibabacloud_iqs20241111.client import Client
        from alibabacloud_tea_openapi import models as open_api_models
    except Exception as exc:
        raise RuntimeError(f"阿里 SDK 未安装或导入失败：{exc}") from exc

    try:
        from Tea.exceptions import TeaException  # type: ignore
    except Exception:
        TeaException = Exception  # type: ignore

    cfg = open_api_models.Config(access_key_id=access_key_id, access_key_secret=access_key_secret)
    cfg.endpoint = "iqs.cn-zhangjiakou.aliyuncs.com"
    client = Client(cfg)

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
    except TeaException as exc:  # type: ignore
        raise RuntimeError(str(exc)) from exc

    page_items: list[dict[str, Any]] = []
    for it in getattr(resp.body, "page_items", []) or []:
        page_items.append(
            {
                "title": getattr(it, "title", None),
                "link": getattr(it, "link", None),
                "snippet": getattr(it, "snippet", None),
                "publishedTime": getattr(it, "published_time", None),
                "mainText": getattr(it, "main_text", None),
                "rerankScore": getattr(it, "rerank_score", None),
            }
        )

    return {"requestId": getattr(resp.body, "request_id", None), "pageItems": page_items}


@router.post("/packs", response_model=MaterialPackOut, summary="创建素材包")
def create_pack(
    payload: MaterialPackCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> MaterialPackOut:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="素材包名称不能为空")

    pack = MaterialPack(
        user_id=current_user.id,
        name=payload.name.strip(),
        description=payload.description,
    )
    db.add(pack)
    db.commit()
    db.refresh(pack)
    return pack


@router.post(
    "/firecrawl-search:ingest",
    response_model=FirecrawlSearchIngestResponse,
    summary="Firecrawl 搜索：一键入库并返回可加入素材篮的条目",
)
def firecrawl_search_ingest(
    payload: FirecrawlSearchIngestRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> FirecrawlSearchIngestResponse:
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    api_key = (payload.api_key or "").strip()
    if not api_key:
        picked = pick_api_key(db, "firecrawl", mark_used=True)
        if picked:
            api_key = (picked.key or "").strip()
    if not api_key:
        import os

        api_key = (os.getenv("FIRECRAWL_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 Firecrawl API Key（可在 APIKey 池或环境变量中配置）")

    sources = payload.sources if isinstance(payload.sources, list) and payload.sources else ["web"]

    # 使用一个系统数据源承载搜索入库的 DataSourceContent，保证追溯链路一致
    ds_name = "Firecrawl 搜索"
    ds = db.query(DataSource).filter(DataSource.name == ds_name).first()
    expected_cfg = {
        "api_mode": "firecrawl_search",
    }
    if not ds:
        ds = DataSource(
            name=ds_name,
            source_type="api",
            config=expected_cfg,
            enable_schedule=False,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
    else:
        # 中文说明：兼容历史版本（曾使用 url + crawler_engine/mode 作为 Firecrawl 搜索模式）。
        # 系统数据源按 name 固定，因此这里可以安全迁移。
        needs_update = False
        if (ds.source_type or "") != "api":
            ds.source_type = "api"
            needs_update = True
        if not isinstance(ds.config, dict) or ds.config.get("api_mode") != "firecrawl_search":
            ds.config = expected_cfg
            needs_update = True
        if ds.enable_schedule:
            ds.enable_schedule = False
            needs_update = True
        if needs_update:
            db.commit()
            db.refresh(ds)

    base_v2 = _normalize_firecrawl_base(payload.api_base)
    endpoint = base_v2.rstrip("/") + "/search"

    body: dict = {
        "query": query,
        "limit": payload.limit,
        "sources": sources,
        "ignoreInvalidURLs": True,
        "scrapeOptions": {
            "formats": ["html"],
        },
    }
    if payload.tbs:
        tbs = payload.tbs.strip()
        if tbs:
            body["tbs"] = tbs

    req_headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(endpoint, json=body, headers=req_headers, timeout=120)
        resp.raise_for_status()
        jd = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Firecrawl 搜索失败：{exc}") from exc

    if not isinstance(jd, dict) or not jd.get("success"):
        raise HTTPException(status_code=400, detail=f"Firecrawl 搜索返回异常：{jd}")

    data = jd.get("data") or {}
    web_items: list[dict] = []
    if isinstance(data, dict):
        for src in sources:
            arr = data.get(src)
            if isinstance(arr, list):
                for idx, it in enumerate(arr):
                    if isinstance(it, dict):
                        it2 = dict(it)
                        it2["_firecrawl_source"] = src
                        it2["_firecrawl_rank"] = idx + 1
                        web_items.append(it2)

    from app.services.readability_extractor import extract_main_text
    from app.services.text_cleaner import clean_text

    ingested = 0
    skipped = 0
    basket_items = []
    seen_content_ids: set[int] = set()

    now_naive = datetime.now()

    for it in web_items:
        url = it.get("url")
        if not isinstance(url, str) or not url.strip():
            skipped += 1
            continue
        url = url.strip()

        raw_html = it.get("html") or it.get("rawHtml") or it.get("markdown")
        if not isinstance(raw_html, str) or not raw_html.strip():
            skipped += 1
            continue

        extract_res = extract_main_text(raw_html, None)
        clean_res = clean_text(extract_res.main_text, None)
        content_text = clean_res.clean_text
        if not (content_text or "").strip():
            skipped += 1
            continue

        title = it.get("title") if isinstance(it.get("title"), str) else None
        url_hash = hashlib.md5(str(url).encode("utf-8", "ignore")).hexdigest()
        last_rec = (
            db.query(DataSourceContent)
            .filter(
                DataSourceContent.datasource_id == ds.id,
                DataSourceContent.url_hash == url_hash,
            )
            .order_by(desc(DataSourceContent.fetched_at))
            .first()
        )
        if last_rec and isinstance(last_rec.extra, dict):
            if last_rec.extra.get("content_hash_clean") == clean_res.content_hash_clean:
                skipped += 1
                # 中文说明：命中去重时仍返回缓存内容
                if last_rec.id not in seen_content_ids:
                    basket_items.append(
                        _build_cached_item(
                            last_rec,
                            title,
                            {
                                "firecrawl_query": query,
                                "firecrawl_rank": it.get("_firecrawl_rank"),
                                "cached": True,
                            },
                        )
                    )
                    seen_content_ids.add(last_rec.id)
                continue

        description = it.get("description") or it.get("snippet")
        meta = it.get("metadata") if isinstance(it.get("metadata"), dict) else {}
        status_code = meta.get("statusCode") if isinstance(meta, dict) else None
        try:
            status_code_int = int(status_code) if status_code is not None else None
        except Exception:
            status_code_int = None

        rec = DataSourceContent(
            user_id=current_user.id,
            datasource_id=ds.id,
            source_type="url",
            title=title or url,
            url=url,
            url_hash=url_hash,
            content=content_text,
            extra={
                "status_code": status_code_int,
                "final_url": meta.get("sourceURL") if isinstance(meta, dict) else None,
                "firecrawl_mode": "search",
                "firecrawl_query": query,
                "firecrawl_source": it.get("_firecrawl_source"),
                "firecrawl_rank": it.get("_firecrawl_rank"),
                "firecrawl_title": title,
                "firecrawl_description": description,
                "content_hash_clean": clean_res.content_hash_clean,
                "clean_stats": clean_res.stats,
                "quality_flags": clean_res.quality_flags,
                "extractor": extract_res.extractor,
                "extractor_meta": extract_res.meta,
            },
            fetched_at=now_naive,
        )
        db.add(rec)
        db.flush()

        ingested += 1
        basket_items.append(
            {
                "item_type": "source",
                "text": (title or url) + "\n" + content_text,
                "source_url": url,
                "source_content_id": rec.id,
                "meta": {
                    "firecrawl_query": query,
                    "firecrawl_rank": it.get("_firecrawl_rank"),
                },
            }
        )
        seen_content_ids.add(rec.id)

    db.commit()

    return FirecrawlSearchIngestResponse(
        ingested=ingested,
        skipped=skipped,
        items=basket_items,
    )


@router.post(
    "/serpapi-search:ingest",
    response_model=SerpapiSearchIngestResponse,
    summary="SerpAPI 搜索：一键入库并返回可加入素材篮的条目",
)
def serpapi_search_ingest(
    payload: SerpapiSearchIngestRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> SerpapiSearchIngestResponse:
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    api_key = (payload.api_key or "").strip()
    if not api_key:
        picked = pick_api_key(db, "serpapi", mark_used=True)
        if picked:
            api_key = (picked.key or "").strip()
    if not api_key:
        api_key = (os.getenv("SERPAPI_API_KEY") or "").strip()
    if not api_key:
        raise HTTPException(status_code=400, detail="未配置 SerpAPI API Key（可在 APIKey 池 provider=serpapi 或环境变量 SERPAPI_API_KEY 中配置）")

    engine = (payload.engine or "google").strip() or "google"
    limit = int(payload.limit or 10)
    limit = max(1, min(100, limit))

    # 使用一个系统数据源承载搜索入库的 DataSourceContent，保证追溯链路一致
    ds_name = "SerpAPI 搜索"
    ds = db.query(DataSource).filter(DataSource.name == ds_name).first()
    expected_cfg = {
        "api_mode": "serpapi_search",
    }
    if not ds:
        ds = DataSource(
            name=ds_name,
            source_type="api",
            config=expected_cfg,
            enable_schedule=False,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
    else:
        # 中文说明：系统数据源按 name 固定，因此这里可以安全迁移。
        needs_update = False
        if (ds.source_type or "") != "api":
            ds.source_type = "api"
            needs_update = True
        if not isinstance(ds.config, dict) or ds.config.get("api_mode") != "serpapi_search":
            ds.config = expected_cfg
            needs_update = True
        if ds.enable_schedule:
            ds.enable_schedule = False
            needs_update = True
        if needs_update:
            db.commit()
            db.refresh(ds)

    try:
        jd = _serpapi_search(
            api_key=api_key,
            query=query,
            engine=engine,
            limit=limit,
            tbs=(payload.tbs or None),
            hl=(payload.hl or None),
            gl=(payload.gl or None),
            location=(payload.location or None),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"SerpAPI 搜索失败：{exc}") from exc

    organic = jd.get("organic_results")
    if not isinstance(organic, list):
        raise HTTPException(status_code=400, detail=f"SerpAPI 返回异常：{jd}")

    from app.services.text_cleaner import clean_text

    ingested = 0
    skipped = 0
    basket_items: list[dict] = []
    seen_content_ids: set[int] = set()
    now_naive = datetime.now()

    for idx, it in enumerate(organic):
        if not isinstance(it, dict):
            skipped += 1
            continue

        url = it.get("link")
        if not isinstance(url, str) or not url.strip():
            skipped += 1
            continue
        url = url.strip()

        title = it.get("title") if isinstance(it.get("title"), str) else None
        snippet = it.get("snippet") if isinstance(it.get("snippet"), str) else None
        raw_text = (snippet or "").strip()
        if not raw_text:
            skipped += 1
            continue

        clean_res = clean_text(raw_text, None)
        content_text = (clean_res.clean_text or "").strip()
        if not content_text:
            skipped += 1
            continue

        url_hash = hashlib.md5(str(url).encode("utf-8", "ignore")).hexdigest()
        last_rec = (
            db.query(DataSourceContent)
            .filter(
                DataSourceContent.datasource_id == ds.id,
                DataSourceContent.url_hash == url_hash,
            )
            .order_by(desc(DataSourceContent.fetched_at))
            .first()
        )
        if last_rec and isinstance(last_rec.extra, dict):
            if last_rec.extra.get("content_hash_clean") == clean_res.content_hash_clean:
                skipped += 1
                # 中文说明：命中去重时仍返回缓存内容
                if last_rec.id not in seen_content_ids:
                    basket_items.append(
                        _build_cached_item(
                            last_rec,
                            title,
                            {
                                "serpapi_rank": idx + 1,
                                "serpapi_engine": engine,
                                "cached": True,
                            },
                        )
                    )
                    seen_content_ids.add(last_rec.id)
                continue

        rec = DataSourceContent(
            user_id=current_user.id,
            datasource_id=ds.id,
            source_type="url",
            title=(title or url),
            url=url,
            url_hash=url_hash,
            content=content_text,
            extra={
                "serpapi_engine": engine,
                "serpapi_query": query,
                "serpapi_rank": idx + 1,
                "serpapi_title": title,
                "serpapi_snippet": snippet,
                "content_hash_clean": clean_res.content_hash_clean,
                "clean_stats": clean_res.stats,
                "quality_flags": clean_res.quality_flags,
            },
            fetched_at=now_naive,
        )
        db.add(rec)
        db.flush()

        ingested += 1
        basket_items.append(
            {
                "item_type": "source",
                "text": (title or url) + "\n" + content_text,
                "source_url": url,
                "source_content_id": rec.id,
                "meta": {
                    "serpapi_rank": idx + 1,
                    "serpapi_engine": engine,
                },
            }
        )
        seen_content_ids.add(rec.id)

    db.commit()

    return SerpapiSearchIngestResponse(
        ingested=ingested,
        skipped=skipped,
        items=basket_items,
    )


@router.post(
    "/aliyun-unified-search:ingest",
    response_model=AliyunUnifiedSearchIngestResponse,
    summary="阿里统一搜索（IQS UnifiedSearch）：一键入库并返回可加入素材篮的条目",
)
def aliyun_unified_search_ingest(
    payload: AliyunUnifiedSearchIngestRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> AliyunUnifiedSearchIngestResponse:
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query 不能为空")

    creds = _resolve_aliyun_iqs_credentials(db)

    ds_name = "阿里统一搜索"
    ds = db.query(DataSource).filter(DataSource.name == ds_name).first()
    expected_cfg = {
        "api_mode": "aliyun_unified_search",
    }
    if not ds:
        ds = DataSource(
            name=ds_name,
            source_type="api",
            config=expected_cfg,
            enable_schedule=False,
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
    else:
        # 中文说明：兼容历史版本（曾使用 url + crawler_engine/mode 作为阿里统一搜索模式）。
        needs_update = False
        if (ds.source_type or "") != "api":
            ds.source_type = "api"
            needs_update = True
        if not isinstance(ds.config, dict) or ds.config.get("api_mode") != "aliyun_unified_search":
            ds.config = expected_cfg
            needs_update = True
        if ds.enable_schedule:
            ds.enable_schedule = False
            needs_update = True
        if needs_update:
            db.commit()
            db.refresh(ds)

    engine_type = (payload.engine_type or "Generic").strip() or "Generic"
    time_range = (payload.time_range or "NoLimit").strip() or "NoLimit"
    category = (payload.category or "").strip() or None
    location = (payload.location or "").strip() or None
    include_main_text = bool(payload.include_main_text) if payload.include_main_text is not None else True
    advanced_params = payload.advanced_params if isinstance(payload.advanced_params, dict) else None

    try:
        if creds["mode"] == "aksk":
            jd = _aliyun_iqs_call_via_sdk(
                query=query,
                engine_type=engine_type,
                time_range=time_range,
                category=category,
                location=location,
                include_main_text=include_main_text,
                advanced_params=advanced_params,
                access_key_id=str(creds.get("access_key_id") or ""),
                access_key_secret=str(creds.get("access_key_secret") or ""),
            )
        else:
            # API Key mode
            jd = _aliyun_iqs_call_via_apikey(
                query=query,
                engine_type=engine_type,
                time_range=time_range,
                category=category,
                location=location,
                include_main_text=include_main_text,
                advanced_params=advanced_params,
                api_key=str(creds.get("api_key") or ""),
                endpoint=str(creds.get("api_endpoint") or ""),
            )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"阿里统一搜索失败（{creds.get('mode')}）：{exc}") from exc

    if not isinstance(jd, dict) or not isinstance(jd.get("pageItems"), list):
        raise HTTPException(status_code=400, detail=f"阿里统一搜索返回异常：{jd}")

    page_items = jd.get("pageItems") or []
    ingested = 0
    skipped = 0
    basket_items: list[dict] = []
    seen_content_ids: set[int] = set()
    now_naive = datetime.now()

    from app.services.text_cleaner import clean_text

    for idx, it in enumerate(page_items):
        if not isinstance(it, dict):
            skipped += 1
            continue

        link = it.get("link")
        if not isinstance(link, str) or not link.strip():
            skipped += 1
            continue
        url = link.strip()

        title = it.get("title") if isinstance(it.get("title"), str) else None
        snippet = it.get("snippet") if isinstance(it.get("snippet"), str) else None
        main_text = it.get("mainText") if isinstance(it.get("mainText"), str) else None
        published_time = it.get("publishedTime") if isinstance(it.get("publishedTime"), str) else None
        rerank_score = it.get("rerankScore")

        raw_text = (main_text or "").strip() or (snippet or "").strip()
        if not raw_text:
            skipped += 1
            continue

        clean_res = clean_text(raw_text, None)
        content_text = (clean_res.clean_text or "").strip()
        if not content_text:
            skipped += 1
            continue

        url_hash = hashlib.md5(str(url).encode("utf-8", "ignore")).hexdigest()
        content_hash = hashlib.md5(str(content_text).encode("utf-8", "ignore")).hexdigest()
        last_rec = (
            db.query(DataSourceContent)
            .filter(
                DataSourceContent.datasource_id == ds.id,
                DataSourceContent.url_hash == url_hash,
            )
            .order_by(desc(DataSourceContent.fetched_at))
            .first()
        )
        if last_rec and isinstance(last_rec.extra, dict):
            if last_rec.extra.get("content_hash") == content_hash:
                skipped += 1
                # 中文说明：命中去重时仍返回缓存内容
                if last_rec.id not in seen_content_ids:
                    basket_items.append(
                        _build_cached_item(
                            last_rec,
                            title,
                            {
                                "iqs_query": query,
                                "iqs_rank": idx + 1,
                                "iqs_engine_type": engine_type,
                                "iqs_time_range": time_range,
                                "cached": True,
                            },
                        )
                    )
                    seen_content_ids.add(last_rec.id)
                continue

        rec = DataSourceContent(
            user_id=current_user.id,
            datasource_id=ds.id,
            source_type="url",
            title=title or url,
            url=url,
            url_hash=url_hash,
            content=content_text,
            extra={
                "iqs_mode": "unified_search",
                "iqs_query": query,
                "iqs_engine_type": engine_type,
                "iqs_time_range": time_range,
                "iqs_category": category,
                "iqs_location": location,
                "iqs_rank": idx + 1,
                "iqs_title": title,
                "iqs_snippet": snippet,
                "iqs_published_time": published_time,
                "iqs_rerank_score": rerank_score,
                "content_hash": content_hash,
                "clean_stats": clean_res.stats,
                "quality_flags": clean_res.quality_flags,
            },
            fetched_at=now_naive,
        )
        db.add(rec)
        db.flush()

        ingested += 1
        basket_items.append(
            {
                "item_type": "source",
                "text": (title or url) + "\n" + content_text,
                "source_url": url,
                "source_content_id": rec.id,
                "meta": {
                    "iqs_query": query,
                    "iqs_rank": idx + 1,
                    "iqs_engine_type": engine_type,
                    "iqs_time_range": time_range,
                },
            }
        )
        seen_content_ids.add(rec.id)

    db.commit()

    return AliyunUnifiedSearchIngestResponse(
        ingested=ingested,
        skipped=skipped,
        items=basket_items,
    )


@router.get("/packs", response_model=MaterialPackListResponse, summary="素材包列表")
def list_packs(
    keyword: Optional[str] = Query(None, description="关键字（name/description）"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> MaterialPackListResponse:
    q = db.query(MaterialPack)
    if not is_admin(current_user):
        q = q.filter(MaterialPack.user_id == current_user.id)
    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.filter((MaterialPack.name.like(kw)) | (MaterialPack.description.like(kw)))

    total = q.count()
    rows = q.order_by(desc(MaterialPack.created_at), desc(MaterialPack.id)).offset(offset).limit(limit).all()
    return MaterialPackListResponse(total=total, limit=limit, offset=offset, items=rows)


@router.get("/packs/{pack_id}", response_model=MaterialPackDetailResponse, summary="素材包详情")
def get_pack(
    pack_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> MaterialPackDetailResponse:
    q = db.query(MaterialPack).filter(MaterialPack.id == pack_id)
    if not is_admin(current_user):
        q = q.filter(MaterialPack.user_id == current_user.id)
    pack = q.first()
    if not pack:
        raise HTTPException(status_code=404, detail="素材包不存在")

    items = (
        db.query(MaterialItem)
        .filter(MaterialItem.pack_id == pack_id)
        .filter(MaterialItem.user_id == pack.user_id)
        .order_by(desc(MaterialItem.created_at), desc(MaterialItem.id))
        .all()
    )
    return MaterialPackDetailResponse(pack=pack, items=items)


@router.delete("/packs/{pack_id}", summary="删除素材包")
def delete_pack(
    pack_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> dict:
    q = db.query(MaterialPack).filter(MaterialPack.id == pack_id)
    if not is_admin(current_user):
        q = q.filter(MaterialPack.user_id == current_user.id)
    pack = q.first()
    if not pack:
        raise HTTPException(status_code=404, detail="素材包不存在")

    try:
        # 中文说明：MaterialItem 通过 pack_id 外键关联；此处先删除子表，避免数据库外键约束问题。
        db.query(MaterialItem).filter(MaterialItem.pack_id == pack_id).delete(synchronize_session=False)
        db.delete(pack)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"删除失败：{exc}") from exc

    return {"ok": True}


@router.post(
    "/packs/{pack_id}/items:batchCreate",
    response_model=list[MaterialItemOut],
    summary="批量追加素材条目",
)
def batch_create_items(
    pack_id: int,
    payload: MaterialItemBatchCreateRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> list[MaterialItemOut]:
    q = db.query(MaterialPack).filter(MaterialPack.id == pack_id)
    if not is_admin(current_user):
        q = q.filter(MaterialPack.user_id == current_user.id)
    pack = q.first()
    if not pack:
        raise HTTPException(status_code=404, detail="素材包不存在")

    created: list[MaterialItem] = []
    for it in payload.items or []:
        if not (it.text or "").strip():
            continue
        item = MaterialItem(
            user_id=pack.user_id,
            pack_id=pack_id,
            item_type=(it.item_type or "").strip().lower(),
            text=_norm_text(it.text),
            text_hash=_hash_item(it.item_type, it.text),
            source_url=it.source_url,
            source_content_id=it.source_content_id,
            source_event_id=it.source_event_id,
            meta=it.meta,
        )
        db.add(item)
        created.append(item)

    db.commit()
    for item in created:
        db.refresh(item)
    return created


@router.patch("/items/{item_id}", response_model=MaterialItemOut, summary="更新素材条目")
def update_item(
    item_id: int,
    payload: MaterialItemUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> MaterialItemOut:
    q = db.query(MaterialItem).filter(MaterialItem.id == item_id)
    if not is_admin(current_user):
        q = q.filter(MaterialItem.user_id == current_user.id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="素材条目不存在")

    if payload.item_type is not None:
        item.item_type = payload.item_type.strip().lower()
    if payload.text is not None:
        item.text = _norm_text(payload.text)
        item.text_hash = _hash_item(item.item_type, item.text)
    if payload.source_url is not None:
        item.source_url = payload.source_url
    if payload.meta is not None:
        item.meta = payload.meta

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/items/{item_id}", summary="删除素材条目")
def delete_item(
    item_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> dict:
    q = db.query(MaterialItem).filter(MaterialItem.id == item_id)
    if not is_admin(current_user):
        q = q.filter(MaterialItem.user_id == current_user.id)
    item = q.first()
    if not item:
        raise HTTPException(status_code=404, detail="素材条目不存在")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/items/search", response_model=MaterialItemSearchResponse, summary="素材条目搜索")
def search_items(
    keyword: Optional[str] = Query(None, description="关键字（text）"),
    pack_id: Optional[int] = Query(None, description="限制某个素材包"),
    item_type: Optional[str] = Query(None, description="过滤条目类型"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> MaterialItemSearchResponse:
    q = db.query(MaterialItem)
    if not is_admin(current_user):
        q = q.filter(MaterialItem.user_id == current_user.id)
    if pack_id is not None:
        q = q.filter(MaterialItem.pack_id == pack_id)
    if item_type:
        q = q.filter(MaterialItem.item_type == item_type.strip().lower())
    if keyword:
        kw = f"%{keyword.strip()}%"
        q = q.filter(MaterialItem.text.like(kw))

    total = q.count()
    rows = q.order_by(desc(MaterialItem.created_at), desc(MaterialItem.id)).offset(offset).limit(limit).all()
    return MaterialItemSearchResponse(total=total, limit=limit, offset=offset, items=rows)


@router.post("/packs/{pack_id}/dedupe", response_model=DedupeResponse, summary="素材包去重")
def dedupe_pack(
    pack_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> DedupeResponse:
    q = db.query(MaterialPack).filter(MaterialPack.id == pack_id)
    if not is_admin(current_user):
        q = q.filter(MaterialPack.user_id == current_user.id)
    pack = q.first()
    if not pack:
        raise HTTPException(status_code=404, detail="素材包不存在")

    rows = (
        db.query(MaterialItem)
        .filter(MaterialItem.pack_id == pack_id)
        .filter(MaterialItem.user_id == pack.user_id)
        .order_by(desc(MaterialItem.created_at), desc(MaterialItem.id))
        .all()
    )

    seen: set[str] = set()
    removed = 0
    for r in rows:
        key = f"{r.item_type}|{r.text_hash}"
        if key in seen:
            db.delete(r)
            removed += 1
            continue
        seen.add(key)

    db.commit()
    return DedupeResponse(removed=removed)
