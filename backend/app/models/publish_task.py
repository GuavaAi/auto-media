from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String

from app.db.base import Base


class PublishTask(Base):
    """发布任务/记录表：用于追踪发布请求、结果与错误，支持后续重试与回放。

    中文说明：
    - provider：平台标识（wechat_official/...）
    - action：动作标识（draft_create/...），后续可扩展到发布、群发、删除、查询等。
    - request/response：保留请求与响应快照，便于排障与回放。
    """

    __tablename__ = "publish_tasks"

    id = Column(Integer, primary_key=True, index=True, comment="主键")

    provider = Column(String(50), nullable=False, index=True, comment="平台标识")
    action = Column(String(50), nullable=False, index=True, comment="动作标识")

    account_id = Column(Integer, nullable=False, index=True, comment="发布账号 ID")
    article_id = Column(Integer, nullable=True, index=True, comment="关联文章 ID（可选）")

    status = Column(String(32), nullable=False, index=True, comment="状态：queued/running/retrying/success/failed/dlq")
    attempts = Column(Integer, nullable=False, default=0, comment="已尝试次数")
    max_attempts = Column(Integer, nullable=False, default=5, comment="最大尝试次数")

    celery_task_id = Column(String(128), nullable=True, index=True, comment="Celery task id（异步队列）")
    next_retry_at = Column(DateTime, nullable=True, comment="下次重试时间（用于展示/调度参考）")
    dlq = Column(Boolean, default=False, nullable=False, comment="是否进入死信队列")

    request = Column(JSON, nullable=True, comment="请求快照")
    response = Column(JSON, nullable=True, comment="响应快照")

    error_code = Column(String(64), nullable=True, comment="错误码（用于分类/重试策略）")
    error_message = Column(String(2000), nullable=True, comment="错误信息")

    remote_id = Column(String(200), nullable=True, index=True, comment="平台返回的资源 ID（如 media_id）")
    remote_url = Column(String(2000), nullable=True, comment="平台返回的 URL（可选）")

    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.now, nullable=False, comment="更新时间")
