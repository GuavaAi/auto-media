"""
数据源相关的数据库操作
封装所有 DataSource 和 DataSourceContent 的数据库查询与持久化逻辑
"""
from datetime import datetime
from typing import Optional, List
import json
import logging

from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.datasource import DataSource
from app.models.datasource_content import DataSourceContent


class DataSourceRepository:
    """DataSource 数据仓库"""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, ds_id: int, user_id: Optional[int] = None) -> Optional[DataSource]:
        """根据 ID 获取数据源，可选按用户过滤"""
        q = self.db.query(DataSource).filter(DataSource.id == ds_id)
        if user_id is not None:
            q = q.filter(DataSource.user_id == user_id)
        return q.first()

    def get_by_name(self, name: str) -> Optional[DataSource]:
        """根据名称获取数据源"""
        return self.db.query(DataSource).filter(DataSource.name == name).first()

    def list_all(self, user_id: Optional[int] = None) -> List[DataSource]:
        """列出所有数据源，可选按用户过滤"""
        q = self.db.query(DataSource)
        if user_id is not None:
            q = q.filter(DataSource.user_id == user_id)
        return q.order_by(DataSource.id.desc()).all()

    def create(self, ds: DataSource) -> DataSource:
        """创建数据源"""
        self.db.add(ds)
        self.db.commit()
        self.db.refresh(ds)
        return ds

    def update(self, ds: DataSource) -> DataSource:
        """更新数据源"""
        self.db.commit()
        self.db.refresh(ds)
        return ds

    def delete(self, ds: DataSource) -> None:
        """删除数据源"""
        self.db.delete(ds)
        self.db.commit()

    def update_run_times(
        self,
        ds: DataSource,
        last_run_at: datetime,
        next_run_at: Optional[datetime],
    ) -> None:
        """更新数据源的运行时间"""
        ds.last_run_at = last_run_at
        ds.next_run_at = next_run_at

    def update_config_with_trigger_report(
        self,
        ds: DataSource,
        trigger_report: dict,
        contents_count: int,
        force: bool,
    ) -> None:
        """
        更新数据源配置，写入触发报告
        注意：SQLAlchemy 的 JSON 字段默认不追踪 dict 原地修改，必须拷贝并标记修改
        """
        cfg = dict(ds.config) if isinstance(ds.config, dict) else {}
        now_naive = datetime.now()
        report_stats = trigger_report.get("stats") if isinstance(trigger_report, dict) else None
        report_skipped = trigger_report.get("skipped_details") if isinstance(trigger_report, dict) else None

        cfg["_last_trigger"] = {
            "triggered_at": now_naive.isoformat(),
            "force": bool(force),
            "ingested": contents_count,
            "stats": report_stats,
            # 控制体积，最多保存 50 条跳过明细
            "skipped_details": (report_skipped[:50] if isinstance(report_skipped, list) else []),
        }
        ds.config = cfg
        flag_modified(ds, "config")


class DataSourceContentRepository:
    """DataSourceContent 数据仓库"""

    def __init__(self, db: Session):
        self.db = db

    def get_latest_by_url_hash(
        self,
        datasource_id: int,
        url_hash: str,
    ) -> Optional[DataSourceContent]:
        """根据 URL 哈希获取最新的内容记录"""
        return (
            self.db.query(DataSourceContent)
            .filter(
                DataSourceContent.datasource_id == datasource_id,
                DataSourceContent.url_hash == url_hash,
            )
            .order_by(desc(DataSourceContent.fetched_at))
            .first()
        )

    def get_parent_record_for_day(
        self,
        datasource_id: int,
        url_hash: str,
        day_start: datetime,
        day_end: datetime,
    ) -> Optional[DataSourceContent]:
        """获取“父页面”当天同 url_hash 的最新记录。

        中文说明：父/子页面通过 extra.is_discovered 区分。
        为了兼容 sqlite/mysql，避免写 JSON 查询表达式，这里先按时间范围查询再在 Python 里过滤。
        """
        recs = (
            self.db.query(DataSourceContent)
            .filter(
                DataSourceContent.datasource_id == datasource_id,
                DataSourceContent.url_hash == url_hash,
                DataSourceContent.fetched_at >= day_start,
                DataSourceContent.fetched_at < day_end,
            )
            .order_by(desc(DataSourceContent.fetched_at))
            .all()
        )
        logger = logging.getLogger(__name__)
        filtered = 0
        for r in recs:
            extra = r.extra
            # 中文说明：兼容历史数据。
            # - 旧记录的 extra 可能为 None / str(JSON)，此时默认认为是“父页面”（is_discovered=False）。
            if isinstance(extra, str):
                try:
                    extra = json.loads(extra)
                except Exception:
                    extra = None

            if not isinstance(extra, dict):
                return r

            # 中文说明：只有明确标记 is_discovered=True 的才当作子页面，其余都视为父页面。
            if not bool(extra.get("is_discovered")):
                return r
            filtered += 1

        if recs and filtered:
            logger.debug(
                f"[get_parent_record_for_day] Found {len(recs)} records for datasource_id={datasource_id} url_hash={url_hash} "
                f"in day range, but all were marked is_discovered=True; day_start={day_start} day_end={day_end}"
            )
        return None

    def update_record(
        self,
        rec: DataSourceContent,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
        extra: Optional[dict] = None,
        fetched_at: Optional[datetime] = None,
    ) -> DataSourceContent:
        """更新内容记录字段（用于手动触发覆盖）。"""
        if title is not None:
            rec.title = title
        if content is not None:
            rec.content = content
        if extra is not None:
            rec.extra = extra
            flag_modified(rec, "extra")
        if fetched_at is not None:
            rec.fetched_at = fetched_at
        return rec

    def exists_by_datasource_id(self, datasource_id: int) -> bool:
        """检查数据源是否已有内容"""
        return (
            self.db.query(DataSourceContent)
            .filter(DataSourceContent.datasource_id == datasource_id)
            .first()
        ) is not None

    def add(self, content: DataSourceContent) -> DataSourceContent:
        """添加内容记录"""
        self.db.add(content)
        return content

    def add_batch(self, contents: List[DataSourceContent]) -> None:
        """批量添加内容记录"""
        for content in contents:
            self.db.add(content)

    def commit(self) -> None:
        """提交事务"""
        self.db.commit()

    def check_dedup(
        self,
        datasource_id: int,
        url_hash: str,
        content_hash: str,
        content_hash_clean: Optional[str],
        force: bool = False,
    ) -> tuple[bool, Optional[DataSourceContent]]:
        """
        检查内容是否重复
        返回: (是否跳过, 匹配的记录)
        """
        if force:
            return False, None

        last_rec = self.get_latest_by_url_hash(datasource_id, url_hash)
        if not last_rec or not isinstance(last_rec.extra, dict):
            return False, None

        # 检查清洗后的内容哈希
        if (
            content_hash_clean
            and last_rec.extra.get("content_hash_clean")
            and last_rec.extra.get("content_hash_clean") == content_hash_clean
        ):
            return True, last_rec

        # 检查原始内容哈希
        if last_rec.extra.get("content_hash") == content_hash:
            return True, last_rec

        return False, None
