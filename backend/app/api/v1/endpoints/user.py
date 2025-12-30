from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import deps
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.user import UserCreate, UserListResponse, UserOut, UserUpdate

router = APIRouter(dependencies=[Depends(deps.require_menu("users"))])


@router.get("/", response_model=UserListResponse, summary="用户列表")
def list_users(db: Session = Depends(deps.get_db)) -> UserListResponse:
    """管理员查看用户列表"""

    rows = db.query(User).order_by(User.id.asc()).all()
    return UserListResponse(
        total=len(rows),
        items=[UserOut.model_validate(r, from_attributes=True) for r in rows],
    )


@router.post("/", response_model=UserOut, summary="创建用户")
def create_user(
    payload: UserCreate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> UserOut:
    """创建新用户"""

    # 中文说明：避免非管理员通过用户管理接口创建 admin 账号造成越权
    if (payload.role or "").lower() == "admin" and (current_user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="无权限创建管理员账号")

    exists = db.query(User).filter(User.username == payload.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")

    row = User(
        username=payload.username,
        full_name=payload.full_name,
        email=payload.email,
        role=payload.role,
        is_active=payload.is_active,
        password_hash=get_password_hash(payload.password),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return UserOut.model_validate(row, from_attributes=True)


@router.patch("/{user_id}", response_model=UserOut, summary="更新用户")
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.require_user),
) -> UserOut:
    """更新用户资料/角色/状态"""

    row = db.query(User).filter(User.id == user_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="用户不存在")

    if row.id == current_user.id:
        if payload.role and payload.role != row.role:
            raise HTTPException(status_code=400, detail="不能修改自己的角色")
        if payload.is_active is False:
            raise HTTPException(status_code=400, detail="不能禁用当前登录账号")

    # 中文说明：避免非管理员把任意用户提升为 admin
    if payload.role is not None:
        if payload.role.lower() == "admin" and (current_user.role or "").lower() != "admin":
            raise HTTPException(status_code=403, detail="无权限设置管理员角色")

    if payload.full_name is not None:
        row.full_name = payload.full_name
    if payload.email is not None:
        row.email = payload.email
    if payload.role is not None:
        row.role = payload.role
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.password:
        row.password_hash = get_password_hash(payload.password)

    db.add(row)
    db.commit()
    db.refresh(row)
    return UserOut.model_validate(row, from_attributes=True)
