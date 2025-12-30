"""
数据源 API 端点
重构后仅保留路由定义，业务逻辑委托给 DataSourceService
"""
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import deps
from app.models.datasource import DataSource
from app.models.user import User
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceOut,
    DataSourceUpdate,
)
from app.services.user_service import is_admin
from app.services.datasource_service import DataSourceService
from app.repositories.datasource_repo import DataSourceRepository

router = APIRouter()


def _compute_next_run(cron_expr: str | None, start_dt: datetime) -> datetime | None:
    if not cron_expr:
        return None
    try:
        from croniter import croniter
    except ImportError:
        return start_dt + timedelta(hours=1)
    try:
        itr = croniter(cron_expr, start_dt)
        return itr.get_next(datetime)
    except Exception:
        return None


# ==================== 兼容层：保留 run_datasource 供 Celery 任务调用 ====================
def run_datasource(
    db: Session, ds: DataSource, force: bool = False, current_user: User | None = None
) -> DataSource:
    """
    执行单个数据源的抓取逻辑（兼容旧接口）
    委托给 DataSourceService 处理
    """
    service = DataSourceService(db)
    try:
        return service.run_datasource(ds, force=force, current_user=current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ==================== API 路由 ====================

@router.get("/", response_model=List[DataSourceOut], summary="数据源列表")
def list_datasources(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> list[DataSource]:
    """列出所有数据源"""
    repo = DataSourceRepository(db)
    user_id = None if is_admin(current_user) else current_user.id
    return repo.list_all(user_id=user_id)


@router.post("/", response_model=DataSourceOut, summary="新增数据源")
def create_datasource(
    payload: DataSourceCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> DataSource:
    """创建数据源，支持不同类型的采集配置"""
    repo = DataSourceRepository(db)

    if payload.name and repo.get_by_name(payload.name):
        raise HTTPException(status_code=400, detail="数据源名称已存在")

    ds = DataSource(
        user_id=current_user.id,
        name=payload.name,
        source_type=payload.source_type,
        config=payload.config,
        biz_category=payload.biz_category,
        schedule_cron=payload.schedule_cron,
        enable_schedule=payload.enable_schedule,
    )
    return repo.create(ds)


@router.delete("/{ds_id}", summary="删除数据源")
def delete_datasource(
    ds_id: int,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> dict:
    """删除数据源"""
    repo = DataSourceRepository(db)
    user_id = None if is_admin(current_user) else current_user.id
    ds = repo.get_by_id(ds_id, user_id=user_id)

    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    repo.delete(ds)
    return {"success": True}


@router.put("/{ds_id}", response_model=DataSourceOut, summary="更新数据源")
def update_datasource(
    ds_id: int,
    payload: DataSourceUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> DataSource:
    """更新数据源"""
    repo = DataSourceRepository(db)
    user_id = None if is_admin(current_user) else current_user.id
    ds = repo.get_by_id(ds_id, user_id=user_id)

    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    # 检查名称是否重复
    if payload.name and payload.name != ds.name:
        existing = repo.get_by_name(payload.name)
        if existing and existing.id != ds_id:
            raise HTTPException(status_code=400, detail="数据源名称已存在")

    schedule_fields_touched = False

    if payload.name is not None:
        ds.name = payload.name
    if payload.source_type is not None:
        ds.source_type = payload.source_type
    if payload.config is not None:
        ds.config = payload.config
    ds.biz_category = payload.biz_category

    if payload.schedule_cron is not None:
        ds.schedule_cron = payload.schedule_cron
        schedule_fields_touched = True
    if payload.enable_schedule is not None:
        ds.enable_schedule = payload.enable_schedule
        schedule_fields_touched = True

    if schedule_fields_touched:
        cron_str = (str(ds.schedule_cron).strip() if ds.schedule_cron is not None else "")
        if ds.enable_schedule and cron_str:
            ds.next_run_at = _compute_next_run(cron_str, datetime.now())
        else:
            ds.next_run_at = None

    return repo.update(ds)


@router.post("/{ds_id}/trigger", response_model=DataSourceOut, summary="手动触发采集并入库原始内容")
def trigger_datasource(
    ds_id: int,
    force: bool = False,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> DataSource:
    """
    手动触发采集：更新 last_run_at，并可选调用 n8n webhook。
    """
    repo = DataSourceRepository(db)
    user_id = None if is_admin(current_user) else current_user.id
    ds = repo.get_by_id(ds_id, user_id=user_id)

    if not ds:
        raise HTTPException(status_code=404, detail="数据源不存在")

    return run_datasource(db, ds, force=force, current_user=current_user)
