# 使 endpoints 目录可被作为包导入
from app.api.v1.endpoints import (  # noqa: F401
    api_key,
    auth,
    crawl_record,
    daily_hotspot,
    dashboard,
    datasource,
    docs,
    generation,
    material,
    publish,
    quick_generate,
    role,
    user,
)
