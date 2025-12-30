from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
import markdown2
from sqlalchemy.orm import Session

from app import deps
from app.models.article import Article
from app.models.prompt_template import PromptTemplate
from app.models.user import User
from app.schemas.article import (
    ArticleAiEditRequest,
    ArticleAiEditResponse,
    ArticleOut,
    ArticleUpdate,
    DeleteResponse,
    GenerationRequest,
)
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateCreateResponse,
    PromptTemplateGetResponse,
    PromptTemplateListResponse,
    PromptTemplateOut,
)
from app.services.generation import generate_article
from app.services.llm_provider import get_provider
from app.services.user_service import is_admin
from app.services.prompt_templates import (
    create_template,
    delete_templates_by_key,
    get_template,
    is_protected_template_key,
)

router = APIRouter()


@router.post(
    "/article",
    response_model=ArticleOut,
    summary="生成公众号软文（Markdown + HTML）",
)
def generate_article_endpoint(
    payload: GenerationRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> ArticleOut:
    """
    生成软文并入库，返回 Markdown 与 HTML，便于复制到公众号后台。
    """
    try:
        return generate_article(db, payload, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/articles", response_model=List[ArticleOut], summary="历史生成列表")
def list_articles(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> list[Article]:
    """查看已生成的文章，按时间倒序"""
    q = db.query(Article)
    if not is_admin(current_user):
        q = q.filter(Article.user_id == current_user.id)
    return q.order_by(Article.id.desc()).all()


@router.get("/articles/{article_id}", response_model=ArticleOut, summary="查看单篇文章")
def get_article(
    article_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> Article:
    """获取单篇文章内容，便于前端复制/预览"""
    q = db.query(Article).filter(Article.id == article_id)
    if not is_admin(current_user):
        q = q.filter(Article.user_id == current_user.id)
    article = q.first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return article


@router.patch(
    "/articles/{article_id}",
    response_model=ArticleOut,
    summary="更新文章（软文管理：编辑保存）",
)
def update_article(
    article_id: int,
    payload: ArticleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> Article:
    q = db.query(Article).filter(Article.id == article_id)
    if not is_admin(current_user):
        q = q.filter(Article.user_id == current_user.id)
    article = q.first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    if payload.title is not None:
        article.title = payload.title
    if payload.summary is not None:
        article.summary = payload.summary

    if payload.content_md is not None:
        article.content_md = payload.content_md

        if payload.content_html is not None:
            article.content_html = payload.content_html
        else:
            article.content_html = markdown2.markdown(payload.content_md)
    elif payload.content_html is not None:
        article.content_html = payload.content_html

    db.add(article)
    db.commit()
    db.refresh(article)
    return article


@router.delete(
    "/articles/{article_id}",
    response_model=DeleteResponse,
    summary="删除文章",
)
def delete_article(
    article_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> DeleteResponse:
    q = db.query(Article).filter(Article.id == article_id)
    if not is_admin(current_user):
        q = q.filter(Article.user_id == current_user.id)
    article = q.first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    db.delete(article)
    db.commit()
    return DeleteResponse(ok=True)


@router.post(
    "/articles/{article_id}/ai-edit",
    response_model=ArticleAiEditResponse,
    summary="AI 重写/续写/翻译（不自动保存）",
)
def ai_edit_article(
    article_id: int,
    payload: ArticleAiEditRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> ArticleAiEditResponse:
    q = db.query(Article).filter(Article.id == article_id)
    if not is_admin(current_user):
        q = q.filter(Article.user_id == current_user.id)
    article = q.first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    action = (payload.action or "").strip().lower()
    if action not in {"rewrite", "continue", "translate"}:
        raise HTTPException(status_code=400, detail="action 仅支持 rewrite/continue/translate")

    instruction = (payload.instruction or "").strip()
    target_language = (payload.target_language or "").strip()
 
    # 确定处理对象：仅处理前端传入的选中片段（不回退整篇文章）
    content = (payload.selected_text or "").strip()
 
    if not content:
        # 续写场景：允许只靠 instruction 生成（相当于从光标处开始写）
        if not (action == "continue" and instruction):
            raise HTTPException(
                status_code=400,
                detail="请先选中需要处理的文本片段（未选中时将不会对整篇文章执行 AI 操作）",
            )

    if action == "rewrite":
        op = "请重写下面的内容，提升表达与结构清晰度，保持 Markdown 格式。"
        if instruction:
            op += f"\n额外要求：{instruction}"
    elif action == "continue":
        op = "请接续下面的内容进行创作，保持上下文连贯，输出 Markdown。"
        if instruction:
            op += f"\n额外要求：{instruction}"
    else:
        if not target_language:
            raise HTTPException(status_code=400, detail="translate 需要提供 target_language")
        op = f"请将下面的内容翻译为 {target_language}，保持 Markdown 结构与语气一致。"
        if instruction:
            op += f"\n额外要求：{instruction}"

    prompt = (
        f"{op}\n\n"
        f"【待处理内容】\n"
        f"{content}\n"
    )
    
    # 补充一些全局上下文信息（如标题），帮助模型理解背景
    prompt += f"\n【背景上下文 - 文章标题】\n{article.title}\n"

    try:
        provider = get_provider(payload.provider, db=db)
        new_md = provider.generate(
            prompt,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            length=payload.length,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    new_md = (new_md or "").strip()
    if not new_md:
        raise HTTPException(status_code=400, detail="模型返回内容为空")

    new_html = markdown2.markdown(new_md)
    return ArticleAiEditResponse(content_md=new_md, content_html=new_html, prompt_text=prompt)


@router.get(
    "/prompt-templates",
    response_model=PromptTemplateListResponse,
    summary="Prompt 模板列表",
)
def list_prompt_templates(
    key: Optional[str] = None,
    name: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    _perm=Depends(deps.require_menu("prompt-templates")),
) -> PromptTemplateListResponse:
    search_q = q
    query = db.query(PromptTemplate)
    if key:
        query = query.filter(PromptTemplate.key == key)
    if name:
        query = query.filter(PromptTemplate.name.contains(name))
    if search_q:
        query = query.filter(
            (PromptTemplate.key.contains(search_q)) | (PromptTemplate.name.contains(search_q))
        )
    rows = query.order_by(
        PromptTemplate.name.asc(),
        PromptTemplate.key.asc(),
        PromptTemplate.version.desc(),
        PromptTemplate.id.desc(),
    ).all()
    return PromptTemplateListResponse(items=rows)


@router.get(
    "/prompt-templates/{key}",
    response_model=PromptTemplateGetResponse,
    summary="获取 Prompt 模板（默认最新版本）",
)
def get_prompt_template(
    key: str,
    version: Optional[int] = None,
    db: Session = Depends(deps.get_db),
    _perm=Depends(deps.require_menu("prompt-templates")),
) -> PromptTemplateGetResponse:
    tpl = get_template(db, key=key, version=version)
    if not tpl:
        raise HTTPException(status_code=404, detail="Prompt 模板不存在")
    return PromptTemplateGetResponse(item=tpl)


@router.post(
    "/prompt-templates",
    response_model=PromptTemplateCreateResponse,
    summary="创建 Prompt 模板新版本（同 key 自动 version+1）",
)
def create_prompt_template(
    payload: PromptTemplateCreate,
    db: Session = Depends(deps.get_db),
    _perm=Depends(deps.require_menu("prompt-templates")),
) -> PromptTemplateCreateResponse:
    tpl = create_template(db, key=payload.key, name=payload.name, content=payload.content)
    db.commit()
    db.refresh(tpl)
    return PromptTemplateCreateResponse(item=tpl)


@router.delete(
    "/prompt-templates/{key}",
    response_model=DeleteResponse,
    summary="删除 Prompt 模板（按 key 删除全部版本）",
)
def delete_prompt_template(
    key: str,
    db: Session = Depends(deps.get_db),
    _perm=Depends(deps.require_menu("prompt-templates")),
) -> DeleteResponse:
    if is_protected_template_key(key):
        raise HTTPException(status_code=403, detail="该模板为系统默认/内置模板，不允许删除")

    deleted = delete_templates_by_key(db, key=key)
    if deleted <= 0:
        raise HTTPException(status_code=404, detail="Prompt 模板不存在")

    db.commit()
    return DeleteResponse(ok=True)
