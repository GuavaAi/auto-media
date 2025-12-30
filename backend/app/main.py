import asyncio
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, SessionLocal
from app.services.user_service import ensure_default_admin
from app.services.role_service import ensure_default_roles
import app.models


if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

settings = get_settings()

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
    
    # 中文说明：确保默认管理员账号存在（若 users 表为空则自动创建）
    db = SessionLocal()
    try:
        ensure_default_roles(db)
        ensure_default_admin(db, get_settings())
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[WARNING] 创建默认管理员失败: {e}")
    finally:
        db.close()


@app.get("/health", summary="健康检查")
def health() -> dict:
    """健康检查接口，便于探活"""
    return {"status": "ok", "env": settings.ENV}


app.include_router(api_router, prefix="/api")
