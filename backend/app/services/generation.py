from typing import List, Optional

import json
from datetime import datetime
import logging
import re
import markdown2
import time
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.datasource import DataSource
from app.models.event_cluster import EventCluster, EventClusterItem
from app.models.material_item import MaterialItem
from app.models.material_pack import MaterialPack
from app.schemas.article import ArticleOut, GenerationRequest
from app.services.llm_provider import get_provider, get_provider_model_name
from app.core.config import get_settings
from app.services.prompt_builder import build_generation_prompt_with_template
from app.services.prompt_templates import ensure_default_template, get_template
from app.services.firecrawl import firecrawl_service


# 注意：直接使用 uvicorn.error logger，确保在本地用 uvicorn 运行时能稳定输出到控制台。
# 若使用 logging.getLogger(__name__)，在未配置 root handler 的情况下，info 日志可能不会显示。
logger = logging.getLogger("uvicorn.error")


def _truncate_for_log(s: str, limit: int) -> str:
    t = (s or "").strip()
    n = int(limit or 0)
    if n <= 0:
        return t
    if len(t) <= n:
        return t
    return t[:n] + "\n...[truncated]"


def _load_source_snippets(
    db: Session, source_ids: Optional[List[int]]
) -> tuple[list[str], list[int]]:
    """根据来源 ID 拉取配置摘要，用于提示模型。"""
    if not source_ids:
        return [], []
    sources = (
        db.query(DataSource).filter(DataSource.id.in_(source_ids)).all()
        if source_ids
        else []
    )
    snippets = []
    found_ids = []
    for src in sources:
        snippets.append(f"{src.name}：{src.config}")
        found_ids.append(src.id)
    return snippets, found_ids


def _load_material_items(db: Session, req: GenerationRequest, *, user_id: int | None = None) -> list[MaterialItem]:
    if not req.material_pack_id:
        return []

    pack = db.query(MaterialPack).filter(MaterialPack.id == req.material_pack_id).first()
    if not pack:
        raise ValueError("素材包不存在")

    # 中文说明：数据隔离——非管理员只能使用自己的素材包生成。
    # user_id 为 None 时表示不做所有权限制（例如：单测或后台任务）。
    if user_id is not None and getattr(pack, "user_id", None) not in {None, user_id}:
        raise ValueError("无权限访问该素材包")

    q = db.query(MaterialItem).filter(MaterialItem.pack_id == req.material_pack_id)
    if req.material_item_ids:
        q = q.filter(MaterialItem.id.in_(req.material_item_ids))

    return q.order_by(MaterialItem.created_at.desc(), MaterialItem.id.desc()).all()


def _load_event_items_to_materials(db: Session, event_id: int) -> list[MaterialItem]:
    """将热点事件条目转换为临时的 MaterialItem 对象，以便复用生成逻辑。"""
    event = db.query(EventCluster).filter(EventCluster.id == event_id).first()
    if not event:
        raise ValueError("指定的热点事件不存在")

    items = (
        db.query(EventClusterItem)
        .filter(EventClusterItem.event_id == event_id)
        .order_by(EventClusterItem.type.asc(), EventClusterItem.position.asc())
        .all()
    )
    
    out = []
    for it in items:
        # 映射字段
        # 注意：id=None (因为不是真实的 MaterialItem 记录), pack_id=None
        m = MaterialItem(
            pack_id=None,
            item_type=it.type,
            text=it.text,
            source_url=it.source_url,
            source_event_id=event_id,
            source_content_id=it.source_content_id,
            meta=it.extra or {},  # 复用 extra
            created_at=datetime.now(),
        )
        out.append(m)
    return out


def _material_cached_layered_summary(it: MaterialItem) -> Optional[dict]:
    meta = getattr(it, "meta", None)
    if not isinstance(meta, dict):
        return None
    ls = meta.get("layered_summary")
    if not isinstance(ls, dict):
        return None
    brief = ls.get("brief")
    bullets = ls.get("bullets")
    if not isinstance(brief, str) or not brief.strip():
        return None
    if bullets is not None and not isinstance(bullets, list):
        return None
    return ls


def _compress_material_text_via_llm(
    *,
    provider,
    topic: str,
    text: str,
    brief_max_chars: int,
    bullet_count: int,
) -> dict:
    """对超长素材做关键内容提取与压缩，返回分层摘要结构。

    返回结构：{"brief": str, "bullets": list[str]}
    """

    safe_brief = max(80, int(brief_max_chars or 180))
    safe_bullets = min(max(3, int(bullet_count or 6)), 12)

    prompt = (
        "你是信息抽取与压缩助手。请从下面的素材中提取关键信息，并压缩为结构化结果。\n"
        "要求：\n"
        f"- 输出一个 JSON 对象，且只输出 JSON（不要输出多余文本）。\n"
        f"- JSON 字段：brief（不超过 {safe_brief} 字），bullets（{safe_bullets} 条要点，数组）。\n"
        "- 内容必须与主题相关，去掉广告、导航、重复段落和无关内容。\n"
        "- bullets 每条尽量包含可验证事实/数据/结论，避免空话。\n\n"
        f"【主题】\n{(topic or '').strip()}\n\n"
        "【待压缩素材】\n"
        f"{(text or '').strip()}\n"
    )

    raw = (provider.generate(prompt, temperature=0.2, max_tokens=1024, length=600) or "").strip()
    if not raw:
        raise ValueError("素材压缩模型返回为空")

    settings = get_settings()
    if bool(getattr(settings, "GENERATION_DEBUG", False)):
        logger.info(
            "[GENERATION_DEBUG] material_compress raw_response (len=%s):\n%s",
            len(raw),
            _truncate_for_log(raw, getattr(settings, "GENERATION_DEBUG_COMPRESS_RAW_MAX_CHARS", 1200)),
        )

    def _extract_json_object(s: str) -> str:
        t = (s or "").strip()
        # 兼容 ```json ... ``` 或 ``` ... ```
        if t.startswith("```"):
            t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\s*```$", "", t)
            t = t.strip()

        # 若仍不是纯 JSON，则尝试截取第一个 { ... } 块
        if not t.startswith("{"):
            m = re.search(r"\{[\s\S]*\}", t)
            if m:
                t = m.group(0).strip()
        return t

    normalized = _extract_json_object(raw)

    try:
        data = json.loads(normalized)
    except Exception as exc:
        raise ValueError(f"素材压缩结果不是有效 JSON：{raw[:200]}") from exc

    if not isinstance(data, dict):
        raise ValueError("素材压缩结果不是 JSON 对象")

    brief = data.get("brief")
    bullets = data.get("bullets")
    if not isinstance(brief, str) or not brief.strip():
        raise ValueError("素材压缩结果缺少 brief")
    if bullets is None:
        bullets = []
    if not isinstance(bullets, list):
        raise ValueError("素材压缩结果 bullets 类型错误")

    clean_bullets: list[str] = []
    for b in bullets:
        if not isinstance(b, str):
            continue
        s = b.strip()
        if not s:
            continue
        clean_bullets.append(s)
        if len(clean_bullets) >= safe_bullets:
            break

    out = {
        "brief": brief.strip()[: safe_brief + 10],
        "bullets": clean_bullets,
    }

    if bool(getattr(settings, "GENERATION_DEBUG", False)):
        logger.info(
            "[GENERATION_DEBUG] material_compress parsed_result: brief=%s bullets=%s",
            out.get("brief"),
            out.get("bullets"),
        )

    return out


def _get_or_create_layered_summary(
    db: Session,
    req: GenerationRequest,
    it: MaterialItem,
    *,
    provider,
    threshold_chars: int,
    brief_max_chars: int,
    bullet_count: int,
) -> Optional[dict]:
    text = (it.text or "").strip()
    if not text:
        return None

    # 短素材：不压缩
    if len(text) <= int(threshold_chars or 0):
        return None

    cached = _material_cached_layered_summary(it)
    if cached and int(cached.get("threshold_chars") or 0) == int(threshold_chars or 0):
        if int(cached.get("brief_max_chars") or 0) == int(brief_max_chars or 0) and int(
            cached.get("bullet_count") or 0
        ) == int(bullet_count or 0):
            settings = get_settings()
            if bool(getattr(settings, "GENERATION_DEBUG", False)):
                logger.info(
                    "[GENERATION_DEBUG] material_compress cache_hit: item_id=%s source_chars=%s brief=%s bullets=%s",
                    getattr(it, "id", None),
                    len(text),
                    cached.get("brief"),
                    cached.get("bullets"),
                )
            return cached

    ls = _compress_material_text_via_llm(
        provider=provider,
        topic=req.topic,
        text=text,
        brief_max_chars=brief_max_chars,
        bullet_count=bullet_count,
    )

    meta = it.meta if isinstance(it.meta, dict) else {}
    meta = dict(meta)
    meta["layered_summary"] = {
        "version": 1,
        "brief": ls.get("brief"),
        "bullets": ls.get("bullets") or [],
        "threshold_chars": int(threshold_chars or 0),
        "brief_max_chars": int(brief_max_chars or 0),
        "bullet_count": int(bullet_count or 0),
        "source_chars": len(text),
        "compressed_at": datetime.now().isoformat(timespec="seconds"),
    }
    it.meta = meta
    
    # 只有当 MaterialItem 是持久化记录时（有 ID），才更新数据库
    # 对于临时的 search items (pack_id=None, id=None)，我们只更新内存对象即可，无需保存
    if it.id is not None:
        db.add(it)
        db.flush()

    settings = get_settings()
    if bool(getattr(settings, "GENERATION_DEBUG", False)):
        logger.info(
            "[GENERATION_DEBUG] material_compress saved: item_id=%s source_chars=%s brief=%s bullets=%s",
            getattr(it, "id", None),
            len(text),
            meta.get("layered_summary", {}).get("brief"),
            meta.get("layered_summary", {}).get("bullets"),
        )
    return meta.get("layered_summary")


def _build_materials_block(items: list[MaterialItem]) -> str:
    """将素材包条目拼成可注入 Prompt 的文本块。

    说明：
    - 支持跨事件/跨来源混合
    - 不强制要求输出引用标注，但会把可用素材清晰地提供给模型
    """
    if not items:
        return ""

    groups: dict[str, list[MaterialItem]] = {}
    for it in items:
        groups.setdefault((it.item_type or "").strip().lower() or "note", []).append(it)

    def _fmt_list(xs: list[MaterialItem], with_url: bool = False) -> str:
        lines: list[str] = []
        for x in xs:
            t = (x.text or "").strip()
            if not t:
                continue
            if with_url and x.source_url:
                lines.append(f"- {t}（{x.source_url}）")
            else:
                lines.append(f"- {t}")
        return "\n".join(lines)

    parts: list[str] = []
    if groups.get("note"):
        parts.append("【我的补充】\n" + _fmt_list(groups["note"]))
    if groups.get("bullet"):
        parts.append("【要点】\n" + _fmt_list(groups["bullet"]))
    if groups.get("fact"):
        parts.append("【事实】\n" + _fmt_list(groups["fact"]))
    if groups.get("quote"):
        parts.append("【引用】\n" + _fmt_list(groups["quote"], with_url=False))
    if groups.get("source"):
        parts.append("【来源】\n" + _fmt_list(groups["source"], with_url=True))

    return "\n\n".join(p for p in parts if p.strip())


def _build_materials_block_layered(
    db: Session,
    req: GenerationRequest,
    items: list[MaterialItem],
    *,
    provider,
) -> str:
    """方案C：将素材构造成“短内容直用 + 长内容分层摘要”的 Prompt 文本块。"""

    if not items:
        return ""

    settings = get_settings()
    threshold_chars = int(getattr(settings, "MATERIAL_COMPRESS_CHAR_THRESHOLD", 1800) or 1800)
    brief_max_chars = int(getattr(settings, "MATERIAL_COMPRESS_BRIEF_MAX_CHARS", 180) or 180)
    bullet_count = int(getattr(settings, "MATERIAL_COMPRESS_BULLET_COUNT", 6) or 6)

    groups: dict[str, list[MaterialItem]] = {}
    for it in items:
        groups.setdefault((it.item_type or "").strip().lower() or "note", []).append(it)

    def _fmt_list(xs: list[MaterialItem], with_url: bool = False) -> str:
        lines: list[str] = []
        for x in xs:
            t = (x.text or "").strip()
            if not t:
                continue

            ls = _get_or_create_layered_summary(
                db,
                req,
                x,
                provider=provider,
                threshold_chars=threshold_chars,
                brief_max_chars=brief_max_chars,
                bullet_count=bullet_count,
            )

            if ls:
                brief = str(ls.get("brief") or "").strip()
                bullets = ls.get("bullets") if isinstance(ls.get("bullets"), list) else []
                bullet_text = "；".join(str(b).strip() for b in bullets if isinstance(b, str) and b.strip())
                content = f"摘要：{brief}"
                if bullet_text:
                    content += f"；要点：{bullet_text}"
            else:
                content = t

            if with_url and x.source_url:
                lines.append(f"- {content}（{x.source_url}）")
            else:
                lines.append(f"- {content}")

        return "\n".join(lines)

    parts: list[str] = []
    if groups.get("note"):
        parts.append("【我的补充】\n" + _fmt_list(groups["note"]))
    if groups.get("bullet"):
        parts.append("【要点】\n" + _fmt_list(groups["bullet"]))
    if groups.get("fact"):
        parts.append("【事实】\n" + _fmt_list(groups["fact"]))
    if groups.get("quote"):
        parts.append("【引用】\n" + _fmt_list(groups["quote"], with_url=False))
    if groups.get("source"):
        parts.append("【来源】\n" + _fmt_list(groups["source"], with_url=True))

    return "\n\n".join(p for p in parts if p.strip())


def generate_article(db: Session, req: GenerationRequest, *, user_id: int | None = None) -> ArticleOut:
    """软文生成主流程：构建 Prompt -> 调用模型 -> 持久化"""
    source_snippets, found_ids = _load_source_snippets(db, req.sources)

    # 先初始化 provider：用于长素材压缩 + 最终生成（避免重复构建/重复选 key）
    provider = get_provider(req.provider, db=db)

    material_items = _load_material_items(db, req, user_id=user_id)
    
    # 支持从热点事件直接加载素材 (Quick Generate)
    if req.source_event_id:
        event_items = _load_event_items_to_materials(db, req.source_event_id)
        # 将事件素材追加到 material_items（或者优先使用）
        material_items.extend(event_items)

    # 支持实时搜索生成 (Active Inspiration)
    if req.source_query:
        # 1. 实时搜索
        search_results = firecrawl_service.search(query=req.source_query, limit=5, db=db)
        # 2. 转换为临时的 MaterialItem
        query_items = []
        for i, res in enumerate(search_results):
            m = MaterialItem(
                pack_id=None,
                item_type="source", # 视为 source 类型
                text=res.get("content") or res.get("description") or "",
                source_url=res.get("url"),
                meta={
                    "title": res.get("title"),
                    "description": res.get("description"),
                    "source": "firecrawl_search",
                },
                created_at=datetime.now(),
            )
            query_items.append(m)
        # 3. 追加到 material_items
        material_items.extend(query_items)

    materials_block = _build_materials_block_layered(db, req, material_items, provider=provider)

    material_refs: Optional[dict] = None
    if material_items:
        item_ids: list[int] = []
        source_urls: list[str] = []
        source_event_ids: list[int] = []
        source_content_ids: list[int] = []
        for it in material_items:
            if it.id is not None:
                item_ids.append(it.id)
            if it.source_url:
                source_urls.append(it.source_url)
            if it.source_event_id is not None:
                source_event_ids.append(it.source_event_id)
            if it.source_content_id is not None:
                source_content_ids.append(it.source_content_id)

        def _uniq(xs):
            seen = set()
            out = []
            for x in xs:
                if x in seen:
                    continue
                seen.add(x)
                out.append(x)
            return out

        material_refs = {
            "item_ids": _uniq(item_ids),
            "source_urls": _uniq(source_urls),
            "source_event_ids": _uniq(source_event_ids),
            "source_content_ids": _uniq(source_content_ids),
        }

    # 将 materials 注入到 req 上，供 prompt_builder 统一渲染模板变量
    # materials 为内部字段（schema 中 exclude=True），前端无需传。
    req.materials = materials_block

    # 1) 选择 Prompt 模板（支持按 key/version 选择；为空则使用默认模板）
    if req.template_key:
        tpl = get_template(db, key=req.template_key, version=req.template_version)
        if not tpl:
            raise ValueError("Prompt 模板不存在，请检查 template_key/template_version")
    else:
        tpl = ensure_default_template(db)

    prompt = build_generation_prompt_with_template(req, tpl.content, source_snippets)

    settings = get_settings()
    if bool(getattr(settings, "GENERATION_DEBUG", False)):
        logger.info(
            "[GENERATION_DEBUG] final_prompt (len=%s):\n%s",
            len(prompt or ""),
            _truncate_for_log(prompt or "", getattr(settings, "GENERATION_DEBUG_PROMPT_MAX_CHARS", 4000)),
        )

    # 2) 调用模型
    t0 = time.perf_counter()
    content_md = provider.generate(
        prompt,
        temperature=req.temperature,
        max_tokens=req.max_tokens,
        length=req.length,
    )
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    # 可选追加行动号召
    if req.call_to_action:
        content_md += f"\n\n**行动号召：{req.call_to_action}**"

    content_html = markdown2.markdown(content_md)
    summary = req.summary_hint or req.topic

    # 3) 生成链路持久化（便于复用/排障）
    request_payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    settings = get_settings()
    llm_provider = (req.provider or settings.DEFAULT_MODEL_PROVIDER).lower()
    llm_model = get_provider_model_name(req.provider)

    article = Article(
        user_id=user_id,
        title=req.topic,
        summary=summary,
        content_md=content_md,
        content_html=content_html,
        source_refs=found_ids or None,
        request_payload=request_payload,
        prompt_text=prompt,
        material_pack_id=req.material_pack_id,
        material_refs=material_refs,
        template_key=tpl.key,
        template_version=tpl.version,
        llm_provider=llm_provider,
        llm_model=llm_model,
        elapsed_ms=elapsed_ms,
        usage=None,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article
