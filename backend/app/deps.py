from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """提供数据库会话的依赖，确保请求结束后关闭连接"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
