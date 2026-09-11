from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import require_user
from app.models.user import User
from app.schemas.friend import (
    FriendRequest, FriendResponse, FriendRequestResponse,
)
from app.services import friend as friend_service
from app.services import user as user_service
from app.models.friend import FriendStatus

router = APIRouter(prefix="/api/friends", tags=["Friends"])


@router.post("/requests", status_code=201)
async def send_request(
    data: FriendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    if data.username == current_user.username:
        raise HTTPException(status_code=400, detail="Cannot add yourself")
    addressee = await user_service.get_user_by_username(db, data.username)
    if not addressee:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        rel = await friend_service.send_friend_request(db, current_user, addressee)
        return {"id": rel.id, "status": rel.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{friend_id}/accept")
async def accept_request(
    friend_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    import uuid
    try:
        fid = uuid.UUID(friend_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid friend ID")
    try:
        rel = await friend_service.accept_friend_request(db, fid)
        return {"id": rel.id, "status": rel.status.value}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/requests/{friend_id}/reject")
async def reject_request(
    friend_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    import uuid
    try:
        fid = uuid.UUID(friend_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid friend ID")
    try:
        await friend_service.reject_friend_request(db, fid)
        return {"message": "Friend request rejected"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{friend_id}", status_code=204)
async def delete_friend(
    friend_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    import uuid
    try:
        fid = uuid.UUID(friend_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid friend ID")
    try:
        await friend_service.delete_friend(db, current_user.id, fid)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/requests", response_model=list[FriendRequestResponse])
async def list_requests(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    requests = await friend_service.get_pending_requests(db, current_user.id)
    result = []
    for req in requests:
        requester = await user_service.get_user_by_id(db, req.requester_id)
        result.append(FriendRequestResponse(
            id=req.id,
            requester_id=req.requester_id,
            requester_username=requester.username,
            requester_display_name=requester.display_name,
            status=req.status,
            created_at=req.created_at,
        ))
    return result


@router.get("", response_model=list[FriendResponse])
async def list_friends(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    friends = await friend_service.get_friends(db, current_user.id)
    result = []
    for friend_user, rel in friends:
        result.append(FriendResponse(
            id=rel.id,
            friend_id=friend_user.id,
            username=friend_user.username,
            display_name=friend_user.display_name,
            avatar_url=friend_user.avatar_url,
            status=rel.status,
            created_at=rel.created_at,
        ))
    return result
