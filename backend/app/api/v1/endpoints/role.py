from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import deps
from app.models.role import Role
from app.models.user import User
from app.schemas.role import RoleCreate, RoleListResponse, RoleOut, RoleUpdate

router = APIRouter(dependencies=[Depends(deps.require_menu("roles"))])


SENSITIVE_MENUS = {
    "api-keys",
    "datasources",
    "prompt-templates",
    "users",
    "roles",
}


@router.get("/", response_model=RoleListResponse, summary="角色列表")
def list_roles(db: Session = Depends(deps.get_db)) -> RoleListResponse:
    rows = db.query(Role).order_by(Role.id.asc()).all()
    return RoleListResponse(total=len(rows), items=[RoleOut.model_validate(r) for r in rows])


@router.post("/", response_model=RoleOut, summary="创建角色")
def create_role(
    payload: RoleCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> RoleOut:
    exists = db.query(Role).filter(Role.key == payload.key).first()
    if exists:
        raise HTTPException(status_code=400, detail="角色 key 已存在")

    if (current_user.role or "").lower() != "admin":
        if any(m in SENSITIVE_MENUS for m in (payload.menus or [])):
            raise HTTPException(status_code=403, detail="无权限配置系统敏感菜单")

    row = Role(key=payload.key, name=payload.name, menus=payload.menus)
    db.add(row)
    db.commit()
    db.refresh(row)
    return RoleOut.model_validate(row)


@router.patch("/{role_id}", response_model=RoleOut, summary="更新角色")
def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> RoleOut:
    row = db.query(Role).filter(Role.id == role_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="角色不存在")

    if payload.name is not None:
        row.name = payload.name
    if payload.menus is not None:
        if (current_user.role or "").lower() != "admin":
            if any(m in SENSITIVE_MENUS for m in (payload.menus or [])):
                raise HTTPException(status_code=403, detail="无权限配置系统敏感菜单")
        row.menus = payload.menus

    db.add(row)
    db.commit()
    db.refresh(row)
    return RoleOut.model_validate(row)


@router.delete("/{role_id}", summary="删除角色")
def delete_role(role_id: int, db: Session = Depends(deps.get_db)) -> dict:
    row = db.query(Role).filter(Role.id == role_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="角色不存在")

    # 中文说明：系统内置角色不允许删除
    if row.key in {"admin", "editor"}:
        raise HTTPException(status_code=400, detail="系统默认角色不允许删除")

    db.delete(row)
    db.commit()
    return {"ok": True}
