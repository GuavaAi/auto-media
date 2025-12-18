from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import asc
from sqlalchemy.orm import Session

from app.models.api_key import ApiKey


def _mask_key(k: str) -> str:
    if not k:
        return ""
    s = str(k)
    if len(s) <= 8:
        return "***"
    return s[:3] + "***" + s[-3:]


def list_api_keys(db: Session, provider: str | None = None) -> list[ApiKey]:
    q = db.query(ApiKey)
    if provider:
        q = q.filter(ApiKey.provider == provider)
    return q.order_by(ApiKey.provider.asc(), ApiKey.id.asc()).all()


def pick_api_key(db: Session, provider: str, *, mark_used: bool = True) -> Optional[ApiKey]:
    """从池子里选取一把可用 key。

    策略：provider 维度下，优先 last_used_at 最早（含 NULL）。
    这是一个轻量的轮询/最久未用优先策略。
    """

    prov = (provider or "").strip().lower()
    if not prov:
        return None

    q = (
        db.query(ApiKey)
        .filter(ApiKey.provider == prov, ApiKey.is_active.is_(True))
        # NULL 表示从未使用：优先；其次按 last_used_at 最早（最久未用）
        .order_by(ApiKey.last_used_at.is_(None).desc(), asc(ApiKey.last_used_at), asc(ApiKey.id))
    )

    key = q.first()
    if not key:
        return None

    if mark_used:
        key.last_used_at = datetime.now()
        key.use_count = int(key.use_count or 0) + 1
        db.add(key)
        db.commit()
        db.refresh(key)

    return key


def masked_out(key: ApiKey) -> str:
    return _mask_key(key.key)
