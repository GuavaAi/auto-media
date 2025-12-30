from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import deps
from app.models.publish_account import PublishAccount
from app.models.publish_task import PublishTask
from app.models.user import User
from app.schemas.publish import PublishAccountCreate, PublishAccountOut, PublishTaskCreateDraftRequest, PublishTaskOut
from app.services.publish.errors import PublishError
from app.services.publish.bootstrap import ensure_providers_registered
from app.services.publish.service import create_draft_task, enqueue_draft_task, retry_task
from app.services.user_service import is_admin


router = APIRouter()


# 中文说明：模块加载即初始化 provider registry，避免在测试或部分运行场景 startup 未触发导致 registry 为空。
ensure_providers_registered()


@router.get("/accounts", response_model=list[PublishAccountOut], summary="发布账号列表")
def list_accounts(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> list[PublishAccount]:
    q = db.query(PublishAccount)
    if not is_admin(current_user):
        q = q.filter(PublishAccount.user_id == current_user.id)
    return q.order_by(PublishAccount.id.desc()).all()


@router.post("/accounts", response_model=PublishAccountOut, summary="创建发布账号")
def create_account(
    payload: PublishAccountCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> PublishAccount:
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="账号名称不能为空")

    acc = PublishAccount(
        user_id=current_user.id,
        name=payload.name.strip(),
        provider=payload.provider.strip(),
        is_active=True,
        config=payload.config,
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return acc


@router.post("/wechat/draft", response_model=PublishTaskOut, summary="微信公众号：创建草稿箱")
def wechat_create_draft(
    payload: PublishTaskCreateDraftRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> PublishTask:
    try:
        ensure_providers_registered()
        return create_draft_task(
            db,
            user_id=current_user.id,
            is_admin=is_admin(current_user),
            account_id=payload.account_id,
            article_id=payload.article_id,
            thumb_image_url=payload.thumb_image_url,
            author=payload.author,
            digest=payload.digest,
            content_source_url=payload.content_source_url,
        )
    except PublishError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/wechat/draft:enqueue", response_model=PublishTaskOut, summary="微信公众号：创建草稿箱（异步队列）")
def wechat_create_draft_enqueue(
    payload: PublishTaskCreateDraftRequest,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> PublishTask:
    try:
        ensure_providers_registered()
        return enqueue_draft_task(
            db,
            user_id=current_user.id,
            is_admin=is_admin(current_user),
            account_id=payload.account_id,
            article_id=payload.article_id,
            thumb_image_url=payload.thumb_image_url,
            author=payload.author,
            digest=payload.digest,
            content_source_url=payload.content_source_url,
        )
    except PublishError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.post("/tasks/{task_id}:retry", response_model=PublishTaskOut, summary="发布任务：手动重试")
def retry_publish_task(
    task_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> PublishTask:
    try:
        ensure_providers_registered()
        return retry_task(db, task_id=task_id, user_id=current_user.id, is_admin=is_admin(current_user))
    except PublishError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/tasks/{task_id}", response_model=PublishTaskOut, summary="发布任务详情")
def get_task(
    task_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> PublishTask:
    q = db.query(PublishTask).filter(PublishTask.id == task_id)
    if not is_admin(current_user):
        q = q.filter(PublishTask.user_id == current_user.id)
    task = q.first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task
