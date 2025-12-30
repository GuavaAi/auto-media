from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import deps
from app.models.api_key import ApiKey
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyListResponse,
    ApiKeyOut,
    ApiKeyPickRequest,
    ApiKeyPickResponse,
    ApiKeyUpdate,
)
from app.services.api_key_pool import masked_out, pick_api_key
from app.services.user_service import is_admin

router = APIRouter()


@router.post("/", response_model=ApiKeyOut, summary="新增 API Key")
def create_api_key(
    payload: ApiKeyCreate,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.require_menu("api-keys")),
) -> ApiKeyOut:
    provider = (payload.provider or "").strip().lower()
    if not provider:
        raise HTTPException(status_code=400, detail="provider 不能为空")
    if not (payload.key or "").strip():
        raise HTTPException(status_code=400, detail="key 不能为空")

    row = ApiKey(
        provider=provider,
        name=(payload.name or None),
        key=payload.key.strip(),
        is_active=bool(payload.is_active),
        extra=payload.extra,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    out = ApiKeyOut.model_validate(row)
    out.key_masked = masked_out(row)
    return out


@router.get("/", response_model=ApiKeyListResponse, summary="API Key 列表")
def list_api_keys(
    provider: str | None = Query(None, description="按 provider 过滤，如 firecrawl"),
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> ApiKeyListResponse:
    prov = (provider or "").strip().lower()

    # 中文说明：API Key 池默认属于敏感配置，仅管理员/有 api-keys 菜单权限的用户可访问。
    # 但数据源管理页需要读取 firecrawl key（用于采集配置），因此对非管理员做特例放行：
    # - 仅允许 provider=firecrawl
    # - 不允许不带 provider（避免枚举全部 key）
    # - 其它 provider 仍保持 403
    if not is_admin(current_user):
        if prov != "firecrawl":
            raise HTTPException(status_code=403, detail="无权限访问")

    q = db.query(ApiKey)
    if prov:
        q = q.filter(ApiKey.provider == prov)
    rows = q.order_by(ApiKey.provider.asc(), ApiKey.id.asc()).all()

    items: list[ApiKeyOut] = []
    for r in rows:
        out = ApiKeyOut.model_validate(r)
        out.key_masked = masked_out(r)
        items.append(out)

    return ApiKeyListResponse(total=len(items), items=items)


@router.patch("/{key_id}", response_model=ApiKeyOut, summary="更新 API Key")
def update_api_key(
    key_id: int,
    payload: ApiKeyUpdate,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.require_menu("api-keys")),
) -> ApiKeyOut:
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API Key 不存在")

    if payload.name is not None:
        row.name = payload.name
    if payload.key is not None:
        if not payload.key.strip():
            raise HTTPException(status_code=400, detail="key 不能为空")
        row.key = payload.key.strip()
    if payload.is_active is not None:
        row.is_active = bool(payload.is_active)

    if payload.extra is not None:
        row.extra = payload.extra

    db.add(row)
    db.commit()
    db.refresh(row)

    out = ApiKeyOut.model_validate(row)
    out.key_masked = masked_out(row)
    return out


@router.delete("/{key_id}", summary="删除 API Key")
def delete_api_key(
    key_id: int,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.require_menu("api-keys")),
) -> dict:
    row = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="API Key 不存在")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/pick", response_model=ApiKeyPickResponse, summary="从池子选取一把可用 Key")
def pick_one(
    payload: ApiKeyPickRequest,
    db: Session = Depends(deps.get_db),
    _: User = Depends(deps.require_menu("api-keys")),
) -> ApiKeyPickResponse:
    provider = (payload.provider or "").strip().lower()
    if not provider:
        raise HTTPException(status_code=400, detail="provider 不能为空")

    k = pick_api_key(db, provider, mark_used=True)
    if not k:
        raise HTTPException(status_code=404, detail=f"未找到可用 key: {provider}")

    return ApiKeyPickResponse(
        id=k.id,
        provider=k.provider,
        key=k.key,
        name=k.name,
        last_used_at=k.last_used_at,
        use_count=k.use_count,
        extra=k.extra,
    )
