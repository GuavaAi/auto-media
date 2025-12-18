from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.publish_account import PublishAccount
from app.models.publish_task import PublishTask
from app.services.publish.errors import PublishError
from app.services.publish.provider_base import PublishResult
from app.services.publish.registry import registry


def _retry_delay_seconds(attempt: int) -> int:
    # 中文说明：指数退避，最大 10 分钟
    base = 10
    delay = base * (2 ** max(0, attempt - 1))
    return int(min(delay, 600))


def create_draft_task(
    db: Session,
    *,
    account_id: int,
    article_id: int,
    thumb_image_url: str,
    author: str | None = None,
    digest: str | None = None,
    content_source_url: str | None = None,
) -> PublishTask:
    account = db.query(PublishAccount).filter(PublishAccount.id == account_id).first()
    if not account or not account.is_active:
        raise PublishError("account_not_found", "发布账号不存在或未启用")

    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise PublishError("article_not_found", "文章不存在")

    provider = registry.get(account.provider)

    now = datetime.now()
    task = PublishTask(
        provider=account.provider,
        action="draft_create",
        account_id=account.id,
        article_id=article.id,
        status="running",
        attempts=0,
        max_attempts=5,
        request={
            "account_id": account.id,
            "article_id": article.id,
            "thumb_image_url": thumb_image_url,
            "author": author,
            "digest": digest,
            "content_source_url": content_source_url,
        },
        response=None,
        remote_id=None,
        remote_url=None,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        task.attempts = int(task.attempts or 0) + 1
        res: PublishResult = provider.create_draft(
            account,
            article,
            thumb_image_url=thumb_image_url,
            author=author,
            digest=digest,
            content_source_url=content_source_url,
        )
        task.status = "success" if res.ok else "failed"
        task.response = res.raw
        task.remote_id = res.remote_id
        task.error_message = None
        task.error_code = None
        task.updated_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    except PublishError as exc:
        task.status = "failed"
        task.error_code = exc.code
        task.error_message = exc.message
        task.response = {"code": exc.code, "detail": exc.detail}
        task.updated_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)
        raise


def enqueue_draft_task(
    db: Session,
    *,
    account_id: int,
    article_id: int,
    thumb_image_url: str,
    author: str | None = None,
    digest: str | None = None,
    content_source_url: str | None = None,
) -> PublishTask:
    """创建发布任务并投递到 Celery。

    中文说明：
    - 该函数不做真实发布，避免 Web 请求阻塞
    - 由 Celery worker 执行实际调用与重试
    """

    account = db.query(PublishAccount).filter(PublishAccount.id == account_id).first()
    if not account or not account.is_active:
        raise PublishError("account_not_found", "发布账号不存在或未启用")

    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise PublishError("article_not_found", "文章不存在")

    now = datetime.now()
    task = PublishTask(
        provider=account.provider,
        action="draft_create",
        account_id=account.id,
        article_id=article.id,
        status="queued",
        attempts=0,
        max_attempts=5,
        celery_task_id=None,
        next_retry_at=None,
        dlq=False,
        request={
            "account_id": account.id,
            "article_id": article.id,
            "thumb_image_url": thumb_image_url,
            "author": author,
            "digest": digest,
            "content_source_url": content_source_url,
        },
        response=None,
        remote_id=None,
        remote_url=None,
        error_code=None,
        error_message=None,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        from app.tasks.publish import run_publish_task

        celery_res = run_publish_task.apply_async(args=[task.id], countdown=0)
        task.celery_task_id = str(getattr(celery_res, "id", None) or "") or None
        task.updated_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)
    except Exception as exc:
        # Celery 不可用时直接失败（任务仍保留，方便手动重试）
        task.status = "failed"
        task.error_code = "celery_enqueue_failed"
        task.error_message = str(exc)
        task.updated_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)
        raise PublishError("celery_enqueue_failed", f"投递队列失败：{exc}") from exc

    return task


def retry_task(db: Session, *, task_id: int) -> PublishTask:
    task = db.query(PublishTask).filter(PublishTask.id == task_id).first()
    if not task:
        raise PublishError("task_not_found", "任务不存在")
    if task.status in {"success"}:
        raise PublishError("bad_status", "任务已成功，无需重试")

    # 重新投递
    task.status = "queued"
    task.dlq = False
    task.next_retry_at = None
    task.error_code = None
    task.error_message = None
    task.updated_at = datetime.now()
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        from app.tasks.publish import run_publish_task

        celery_res = run_publish_task.apply_async(args=[task.id], countdown=0)
        task.celery_task_id = str(getattr(celery_res, "id", None) or "") or None
        task.updated_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)
    except Exception as exc:
        raise PublishError("celery_enqueue_failed", f"投递队列失败：{exc}") from exc

    return task
