from fastapi import APIRouter, Depends

from app import deps

from app.api.v1.endpoints import (
    auth,
    crawl_record,
    datasource,
    generation,
    daily_hotspot,
    dashboard,
    material,
    api_key,
    utils,
    docs,
    publish,
    quick_generate,
    user,
)

api_router = APIRouter()

require_user_dep = [Depends(deps.require_user)]

# 仪表盘
api_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["仪表盘"],
    dependencies=require_user_dep,
)

# 鉴权
api_router.include_router(auth.router, prefix="/auth", tags=["鉴权"])

# 素材库（素材包/条目/搜索/去重）
api_router.include_router(
    material.router,
    prefix="/materials",
    tags=["素材库"],
    dependencies=require_user_dep,
)

# 发布（多平台，当前先支持公众号草稿箱）
api_router.include_router(
    publish.router,
    prefix="/publish",
    tags=["发布"],
    dependencies=require_user_dep,
)

# API Key 池
api_router.include_router(
    api_key.router,
    prefix="/api-keys",
    tags=["API Key 池"],
    dependencies=require_user_dep,
)

# 工具接口（预览/调试）
api_router.include_router(
    utils.router,
    prefix="/utils",
    tags=["工具"],
    dependencies=require_user_dep,
)

# 文档（运营手册等）
api_router.include_router(
    docs.router,
    prefix="/docs",
    tags=["文档"],
    dependencies=require_user_dep,
)

# 数据源管理（后续可扩展采集任务）
api_router.include_router(
    datasource.router,
    prefix="/datasources",
    tags=["数据源"],
    dependencies=require_user_dep,
)

api_router.include_router(
    crawl_record.router,
    prefix="/crawl-records",
    tags=["采集记录"],
    dependencies=require_user_dep,
)

# 软文生成与导出
api_router.include_router(
    generation.router,
    prefix="/generate",
    tags=["内容生成"],
    dependencies=require_user_dep,
)

api_router.include_router(
    daily_hotspot.router,
    prefix="/daily-hotspots",
    tags=["热点榜单"],
    dependencies=require_user_dep,
)

# 一键生成 (Quick Draft)
api_router.include_router(
    quick_generate.router,
    prefix="/quick-generate",
    tags=["一键生成"],
    dependencies=require_user_dep,
)

# 用户管理
api_router.include_router(user.router, prefix="/users", tags=["用户管理"])
