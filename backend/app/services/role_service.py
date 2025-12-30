from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from app.models.role import Role


DEFAULT_ADMIN_MENUS: list[str] = [
    "dashboard",
    "quickstart",
    "config-guide",
    "generate",
    "articles",
    "materials",
    "publish",
    "daily-hotspots",
    "crawl-records",
    "datasources",
    "prompt-templates",
    "api-keys",
    "users",
    "roles",
]

DEFAULT_EDITOR_MENUS: list[str] = [
    "dashboard",
    "quickstart",
    "config-guide",
    "generate",
    "articles",
    "materials",
    "publish",
    "daily-hotspots",
    "crawl-records",
]


def ensure_default_roles(db: Session) -> None:
    """确保系统默认角色存在。

    中文说明：
    - admin 默认拥有全部菜单
    - editor 默认仅拥有内容生产/数据采集等基础菜单
    """

    _ensure_role(db, key="admin", name="管理员", menus=DEFAULT_ADMIN_MENUS)
    _ensure_role(db, key="editor", name="成员", menus=DEFAULT_EDITOR_MENUS)


def _ensure_role(db: Session, key: str, name: str, menus: Iterable[str]) -> None:
    row = db.query(Role).filter(Role.key == key).first()
    if row:
        return

    db.add(Role(key=key, name=name, menus=list(menus)))


def get_role_menus(db: Session, role_key: str | None) -> list[str]:
    key = (role_key or "").strip()
    if not key:
        return []

    row = db.query(Role).filter(Role.key == key).first()
    if not row:
        # 中文说明：兼容 roles 表尚未初始化的场景（如部分测试/首次启动）
        if key.lower() == "admin":
            return DEFAULT_ADMIN_MENUS
        if key.lower() == "editor":
            return DEFAULT_EDITOR_MENUS
        return []

    menus = row.menus or []
    if isinstance(menus, list):
        return [str(x) for x in menus]
    return []
