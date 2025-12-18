from __future__ import annotations

from app.services.publish.registry import registry
from app.services.publish.wechat_official import provider_singleton


_registered = False


def ensure_providers_registered() -> None:
    """确保 Provider 已注册。

    中文说明：
    - Web 进程与 Celery worker 都可能需要 provider registry。
    - 避免依赖 FastAPI startup 事件，统一在需要时显式调用。
    """

    global _registered
    if _registered:
        return
    try:
        registry.register(provider_singleton)
    except Exception:
        # 重复注册等异常都忽略
        pass
    _registered = True
