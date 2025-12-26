from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models.user import User
from app.services.user_service import ensure_default_admin, is_admin

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    """提供数据库会话的依赖，确保请求结束后关闭连接"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db), token: str | None = Depends(oauth2_scheme)
) -> User:
    """解析并返回当前用户，若关闭鉴权则回退为默认管理员"""

    settings = get_settings()

    # 开发模式可通过 DISABLE_AUTH_GUARD=true 跳过鉴权（仍保证至少有一个管理员）
    if settings.DISABLE_AUTH_GUARD:
        user = db.query(User).order_by(User.id.asc()).first()
        if user:
            return user
        return ensure_default_admin(db, settings)

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少身份凭证")

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")

    return user


def require_user(user: User = Depends(get_current_user)) -> User:
    """通用登录校验"""

    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """管理员校验"""

    if not is_admin(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅管理员可执行此操作")
    return user
