import asyncio
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine
import app.models


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

settings = get_settings()


def _ensure_publish_tasks_schema() -> None:
    """开发环境下的轻量 schema 自修复。

    中文说明：
    - 目前项目未引入 Alembic 迁移，历史数据库可能缺少新增字段（例如 max_attempts）。
    - 这里仅做“缺什么补什么”的 ADD COLUMN，避免 publish 入队/更新状态时 commit 失败。
    """

    inspector = inspect(engine)
    if "publish_tasks" not in set(inspector.get_table_names()):
        return

    cols = {c.get("name") for c in inspector.get_columns("publish_tasks")}

    # 仅补齐缺失列（MySQL 语法），避免破坏已有数据
    alter_sqls: list[str] = []
    if "max_attempts" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN max_attempts INT NOT NULL DEFAULT 5")
    if "celery_task_id" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN celery_task_id VARCHAR(128) NULL")
    if "next_retry_at" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN next_retry_at DATETIME NULL")
    if "dlq" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN dlq TINYINT(1) NOT NULL DEFAULT 0")
    if "request" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN request JSON NULL")
    if "response" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN response JSON NULL")
    if "error_code" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN error_code VARCHAR(64) NULL")
    if "error_message" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN error_message VARCHAR(2000) NULL")
    if "remote_id" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN remote_id VARCHAR(200) NULL")
    if "remote_url" not in cols:
        alter_sqls.append("ALTER TABLE publish_tasks ADD COLUMN remote_url VARCHAR(2000) NULL")

    if not alter_sqls:
        return

    with engine.begin() as conn:
        for sql in alter_sqls:
            conn.execute(text(sql))

app = FastAPI(title=settings.PROJECT_NAME, version="0.1.0")

# CORS，前端本地调试时允许跨域与预检 OPTIONS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """启动时创建表，方便本地快速体验"""
    Base.metadata.create_all(bind=engine)
    _ensure_publish_tasks_schema()


@app.get("/health", summary="健康检查")
def health() -> dict:
    """健康检查接口，便于探活"""
    return {"status": "ok", "env": settings.ENV}


app.include_router(api_router, prefix="/api")
