from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Protocol

import redis

from app.core.config import get_settings


@dataclass
class TokenValue:
    token: str
    expires_at: float


class TokenCache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, token: str, ttl_seconds: int) -> None: ...


class InMemoryTokenCache:
    """简单内存 token cache。

    中文说明：
    - 本地开发/单测可用
    - 生产建议替换为 Redis（后续可扩展）
    """

    def __init__(self) -> None:
        self._store: dict[str, TokenValue] = {}

    def get(self, key: str) -> str | None:
        v = self._store.get(key)
        if not v:
            return None
        if v.expires_at <= time.time():
            self._store.pop(key, None)
            return None
        return v.token

    def set(self, key: str, token: str, ttl_seconds: int) -> None:
        ttl_seconds = max(1, int(ttl_seconds))
        self._store[key] = TokenValue(token=token, expires_at=time.time() + ttl_seconds)


class RedisTokenCache:
    """Redis token cache。

    中文说明：
    - 用于多进程/多实例共享 access_token
    - Redis 不可用时不应阻塞主流程：会自动降级到 fallback
    """

    def __init__(
        self,
        redis_url: str,
        *,
        key_prefix: str = "token:",
        fallback: TokenCache | None = None,
    ) -> None:
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self._key_prefix = key_prefix
        self._fallback = fallback or InMemoryTokenCache()

    def _k(self, key: str) -> str:
        return f"{self._key_prefix}{key}"

    def get(self, key: str) -> str | None:
        try:
            v = self._redis.get(self._k(key))
            if isinstance(v, str) and v:
                return v
        except Exception:
            return self._fallback.get(key)
        return None

    def set(self, key: str, token: str, ttl_seconds: int) -> None:
        ttl_seconds = max(1, int(ttl_seconds))
        try:
            # setex: 原子写入 + 过期
            self._redis.setex(self._k(key), ttl_seconds, token)
            return
        except Exception:
            self._fallback.set(key, token, ttl_seconds)


def build_token_cache() -> TokenCache:
    """根据配置构建 token cache。

    中文说明：
    - 默认使用 Redis（settings.REDIS_URL）
    - Redis 不可用时会在 RedisTokenCache 内自动降级到内存
    """

    settings = get_settings()

    # 中文说明：pytest 环境下不依赖外部 Redis，避免连接开销与不稳定。
    if os.getenv("PYTEST_CURRENT_TEST"):
        return InMemoryTokenCache()

    redis_url = (getattr(settings, "REDIS_URL", None) or "").strip()
    if redis_url:
        return RedisTokenCache(redis_url, key_prefix="auto_media:")
    return InMemoryTokenCache()
