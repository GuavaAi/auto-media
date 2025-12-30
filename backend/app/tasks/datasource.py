from __future__ import annotations

from datetime import datetime, timedelta

from celery import shared_task
from sqlalchemy.orm import Session

from app.services.datasource_service import DataSourceService
from app.db.session import SessionLocal
from app.models.datasource import DataSource


def _compute_next_run(cron_expr: str | None, start_dt: datetime) -> datetime | None:
    """基于 cron 表达式计算下一次时间，失败则返回 None。"""
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


@shared_task(name="app.tasks.datasource.trigger_datasource_task")
def trigger_datasource_task(ds_id: int, force: bool = False) -> dict:
    """异步任务：触发单个数据源抓取（供手动/调度调用）。"""
    db: Session = SessionLocal()
    try:
        ds = db.query(DataSource).filter(DataSource.id == ds_id).first()
        if not ds:
            return {"status": "not_found", "id": ds_id}
        service = DataSourceService(db)
        service.run_datasource(ds, force=force, current_user=None)
        return {"status": "ok", "id": ds_id}
    except Exception as exc:
        db.rollback()
        return {"status": "error", "id": ds_id, "error": str(exc)}
    finally:
        db.close()


@shared_task(name="app.tasks.datasource.scan_and_trigger_datasources")
def scan_and_trigger_datasources() -> dict:
    """
    每分钟扫描启用定时的数据源：
    - 满足 enable_schedule 且 schedule_cron 不为空
    - 当 next_run_at 到期（<= now）或未设置 next_run_at 时，触发抓取
    """
    import logging
    logger = logging.getLogger(__name__)
    
    db: Session = SessionLocal()
    now = datetime.now()
    triggered: list[int] = []
    skipped: list[dict] = []
    errors: list[dict] = []
    total_scanned = 0
    skipped_not_due = 0
    
    try:
        # 过滤掉空 cron 或未启用的
        ds_list = (
            db.query(DataSource)
            .filter(DataSource.enable_schedule.is_(True))
            .filter(DataSource.schedule_cron.isnot(None))
            .filter(DataSource.schedule_cron != "")
            .all()
        )
        total_scanned = len(ds_list)
        
        service = DataSourceService(db)
        for ds in ds_list:
            try:
                # 再次校验 cron 字符串有效性
                cron_str = str(ds.schedule_cron).strip()
                if not cron_str:
                    skipped.append({"id": ds.id, "name": ds.name, "reason": "empty_cron"})
                    continue
                
                # 如果未预先计算 next_run_at，则用 last_run_at（或当前）推算
                base_dt = ds.next_run_at or ds.last_run_at or now
                next_run = ds.next_run_at or _compute_next_run(cron_str, base_dt)
                
                if not next_run:
                    skipped.append({"id": ds.id, "name": ds.name, "reason": "next_run_none"})
                    continue
                
                if next_run > now:
                    skipped_not_due += 1
                    skipped.append(
                        {
                            "id": ds.id,
                            "name": ds.name,
                            "reason": "not_due",
                            "next_run_at": next_run.isoformat(),
                        }
                    )
                    continue
                
                logger.info(f"[Scheduler] Triggering datasource {ds.id} ({ds.name}), due at {next_run}")
                service.run_datasource(ds, force=False, current_user=None)
                triggered.append(ds.id)
            except Exception as exc:
                db.rollback()
                logger.error(f"[Scheduler] Error triggering datasource {ds.id}: {str(exc)}")
                errors.append({"id": ds.id, "name": ds.name, "error": str(exc)})
    finally:
        db.close()
    
    result = {
        "scanned": total_scanned,
        "triggered": triggered,
        "skipped_not_due": skipped_not_due,
        "skipped": skipped,
        "errors": errors,
        "timestamp": now.isoformat()
    }
    logger.info(f"[Scheduler] Scan complete: {len(triggered)} triggered, {skipped_not_due} skipped, {len(errors)} errors.")
    return result
