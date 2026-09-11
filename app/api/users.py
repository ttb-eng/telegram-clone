from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import require_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services import user as user_service

router = APIRouter(prefix="/api/users", tags=["Users"])

#获取自己的信息
@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(require_user)):
    return UserResponse.model_validate(current_user)

#更新自己的信息
@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    user = await user_service.update_user(db, current_user, data)
    return UserResponse.model_validate(user)

#搜索用户（排除自己）

@router.get("/search", response_model=list[UserResponse])
async def search_users(
    q: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    users = await user_service.search_users(db, q)
    return [UserResponse.model_validate(u) for u in users if u.id != current_user.id]

#查看指定用户的信息
@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    user = await user_service.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse.model_validate(user)


@router.delete("/me", status_code=204)
async def delete_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    await user_service.delete_user(db, current_user)
    return

@router.delete("/{user_id}", status_code=204)
async def delete_user_by_admin(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),  # 需要登录
):
    # 这里应该增加管理员权限检查，例如 if not current_user.is_admin: raise 403
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(400, "Invalid user ID")
    user = await user_service.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(404, "User not found")
    await user_service.delete_user(db, user)
