from __future__ import annotations

from datetime import datetime, timedelta

from app.celery_app import celery_app

from app.db.session import SessionLocal
from app.models.article import Article
from app.models.publish_account import PublishAccount
from app.models.publish_task import PublishTask
from app.services.publish.bootstrap import ensure_providers_registered
from app.services.publish.errors import PublishError
from app.services.publish.registry import registry


def _retry_delay_seconds(attempt: int) -> int:
    base = 10
    delay = base * (2 ** max(0, attempt - 1))
    return int(min(delay, 600))


@celery_app.task(name="app.tasks.publish.run_publish_task")
def run_publish_task(publish_task_id: int) -> dict:
    """Celery 发布任务执行器（当前仅草稿箱）。

    中文说明：
    - 失败时指数退避重试，超过 max_attempts 进入 DLQ。
    - 所有状态/错误会回写 publish_tasks 表，保证可追踪、可回放。
    """

    ensure_providers_registered()

    db = SessionLocal()
    try:
        task = db.query(PublishTask).filter(PublishTask.id == int(publish_task_id)).first()
        if not task:
            return {"status": "skipped", "reason": "task_not_found"}

        if task.status == "success":
            return {"status": "ok", "task_id": task.id, "already": True}

        account = db.query(PublishAccount).filter(PublishAccount.id == task.account_id).first()
        if not account or not account.is_active:
            raise PublishError("account_not_found", "发布账号不存在或未启用")

        article = None
        if task.article_id is not None:
            article = db.query(Article).filter(Article.id == task.article_id).first()
        if not article:
            raise PublishError("article_not_found", "文章不存在")

        provider = registry.get(account.provider)

        # 更新状态
        task.status = "running"
        task.updated_at = datetime.now()
        db.add(task)
        db.commit()
        db.refresh(task)

        # 执行动作
        if task.action == "draft_create":
            req = task.request if isinstance(task.request, dict) else {}
            res = provider.create_draft(
                account,
                article,
                thumb_image_url=str(req.get("thumb_image_url") or ""),
                author=req.get("author"),
                digest=req.get("digest"),
                content_source_url=req.get("content_source_url"),
            )
            task.status = "success"
            task.response = res.raw
            task.remote_id = res.remote_id
            task.error_code = None
            task.error_message = None
            task.next_retry_at = None
            task.updated_at = datetime.now()
            db.add(task)
            db.commit()
            db.refresh(task)
            return {"status": "ok", "task_id": task.id, "remote_id": task.remote_id}

        raise PublishError("bad_action", f"不支持的 action: {task.action}")

    except PublishError as exc:
        # 失败：写入错误并决定是否重试
        try:
            task = db.query(PublishTask).filter(PublishTask.id == int(publish_task_id)).first()
            if not task:
                return {"status": "failed", "reason": "task_not_found"}

            task.attempts = int(task.attempts or 0) + 1
            task.error_code = exc.code
            task.error_message = exc.message
            task.response = {"code": exc.code, "detail": exc.detail}

            if task.attempts < int(task.max_attempts or 5):
                delay = _retry_delay_seconds(task.attempts)
                task.status = "retrying"
                task.next_retry_at = datetime.now() + timedelta(seconds=delay)
                task.updated_at = datetime.now()
                db.add(task)
                db.commit()
                db.refresh(task)

                # 重新投递自身（指数退避）
                run_publish_task.apply_async(args=[publish_task_id], countdown=delay)
                return {"status": "retrying", "task_id": task.id, "delay": delay}

            task.status = "dlq"
            task.dlq = True
            task.next_retry_at = None
            task.updated_at = datetime.now()
            db.add(task)
            db.commit()
            db.refresh(task)
            return {"status": "dlq", "task_id": task.id}
        except Exception:
            db.rollback()
            return {"status": "failed", "task_id": publish_task_id}

    except Exception as exc:
        # 中文说明：兜底异常也要写回数据库，否则前端看到的仍是 queued/running，导致“没任何返回”的错觉。
        try:
            db.rollback()
            task = db.query(PublishTask).filter(PublishTask.id == int(publish_task_id)).first()
            if task:
                task.attempts = int(task.attempts or 0) + 1
                task.status = "failed"
                task.error_code = "unexpected_error"
                task.error_message = str(exc)
                task.response = {"error": str(exc)}
                task.updated_at = datetime.now()
                db.add(task)
                db.commit()
                db.refresh(task)
        except Exception:
            db.rollback()
        return {"status": "failed", "error": str(exc)}

    finally:
        db.close()
