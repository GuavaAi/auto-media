from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import redis
from sqlalchemy import create_engine, text


def _wait_for_mysql(mysql_url: str, timeout_seconds: int = 90) -> None:
    """等待 MySQL 可用。

    中文说明：
    - Docker 场景下 backend 可能比 mysql 容器更早启动。
    - 如果不做等待，FastAPI 启动时 create_all 连接数据库会直接失败并退出。
    """

    deadline = time.time() + timeout_seconds
    last_err: Exception | None = None

    while time.time() < deadline:
        try:
            engine = create_engine(mysql_url, pool_pre_ping=True, future=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2)

    raise RuntimeError(f"MySQL 连接超时（{timeout_seconds}s）：{last_err}")


def _wait_for_redis(redis_url: str, timeout_seconds: int = 60) -> None:
    """等待 Redis 可用。"""

    deadline = time.time() + timeout_seconds
    last_err: Exception | None = None

    parsed = urlparse(redis_url)
    host = parsed.hostname or "redis"
    port = parsed.port or 6379
    db = int((parsed.path or "/0").lstrip("/") or "0")

    while time.time() < deadline:
        try:
            client = redis.Redis(host=host, port=port, db=db, socket_connect_timeout=2)
            client.ping()
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(1)

    raise RuntimeError(f"Redis 连接超时（{timeout_seconds}s）：{last_err}")


def main() -> None:
    mysql_url = os.getenv("MYSQL_URL")
    redis_url = os.getenv("REDIS_URL")

    if mysql_url:
        _wait_for_mysql(mysql_url)

    if redis_url:
        _wait_for_redis(redis_url)


if __name__ == "__main__":
    main()
