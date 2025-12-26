from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import get_password_hash
from app.models.user import User


def ensure_default_admin(db: Session, settings: Optional[Settings] = None) -> User:
    """确保至少存在一个管理员账号（用于首登）。

    - 若用户表已有 admin，则直接返回
    - 否则基于环境变量创建默认管理员
    """

    settings = settings or get_settings()
    admin = (
        db.query(User)
        .filter(User.username == settings.DEFAULT_ADMIN_USERNAME)
        .order_by(User.id.asc())
        .first()
    )
    if admin:
        return admin

    admin = User(
        username=settings.DEFAULT_ADMIN_USERNAME,
        full_name="系统管理员",
        email=settings.DEFAULT_ADMIN_EMAIL,
        role="admin",
        password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


def is_admin(user: User) -> bool:
    """简单判断角色"""

    return (user.role or "").lower() == "admin"
