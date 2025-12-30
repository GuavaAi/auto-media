from datetime import datetime

from sqlalchemy import Boolean, JSON, Column, DateTime, ForeignKey, Integer, String

from app.db.base import Base


class DataSource(Base):
    """数据源信息表，记录采集入口与配置"""

    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True, comment="主键")

    # 中文说明：用于数据隔离。非管理员默认只能访问自己创建的数据源。
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True, comment="创建者用户 ID")

    name = Column(String(100), unique=True, nullable=False, comment="数据源名称")
    source_type = Column(
        String(50), nullable=False, comment="数据源类型，如 url/api/document/n8n"
    )
    config = Column(JSON, nullable=True, comment="采集配置 JSON，含 n8n webhook 等")
    biz_category = Column(String(100), nullable=True, comment="业务分类")
    schedule_cron = Column(String(100), nullable=True, comment="定时抓取 cron 表达式")
    enable_schedule = Column(Boolean, default=False, nullable=False, comment="是否启用定时抓取")
    last_run_at = Column(DateTime, nullable=True, comment="上次抓取时间")
    next_run_at = Column(DateTime, nullable=True, comment="下次计划时间")
    created_at = Column(DateTime, default=datetime.now, nullable=False, comment="创建时间")
