from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import deps
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.user import AuthLoginRequest, AuthLoginResponse, AuthProfileResponse, UserOut
from app.services.user_service import ensure_default_admin

router = APIRouter()


@router.post("/login", response_model=AuthLoginResponse, summary="用户登录")
def login(payload: AuthLoginRequest, db: Session = Depends(deps.get_db)) -> AuthLoginResponse:
    """校验用户名密码，返回 JWT 令牌"""

    ensure_default_admin(db)

    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

    token = create_access_token({"sub": str(user.id), "username": user.username, "role": user.role})
    return AuthLoginResponse(
        access_token=token,
        user=UserOut.model_validate(user, from_attributes=True),
    )


@router.get("/profile", response_model=AuthProfileResponse, summary="获取当前登录用户")
def profile(user: User = Depends(deps.require_user)) -> AuthProfileResponse:
    """返回当前登录用户信息"""

    return AuthProfileResponse(user=UserOut.model_validate(user, from_attributes=True))
