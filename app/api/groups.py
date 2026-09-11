import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import require_user
from app.models.user import User
from app.schemas.group import (
    GroupCreate, GroupUpdate, GroupResponse, GroupDetailResponse,
    GroupMemberResponse, AddMemberRequest,
)
from app.schemas.message import MessageResponse
from app.services import group as group_service
from app.services import user as user_service

router = APIRouter(prefix="/api/groups", tags=["Groups"])


@router.post("", status_code=201, response_model=GroupResponse)
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    group = await group_service.create_group(
        db, current_user, data.name, data.description, data.member_ids
    )
    members = await group_service.get_members(db, group.id)
    resp = GroupResponse.model_validate(group)
    resp.member_count = len(members)
    return resp


@router.get("", response_model=list[GroupResponse])
async def list_groups(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    groups = await group_service.get_user_groups(db, current_user.id)
    result = []
    for g in groups:
        members = await group_service.get_members(db, g.id)
        resp = GroupResponse.model_validate(g)
        resp.member_count = len(members)
        result.append(resp)
    return result


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = await group_service.get_group(db, gid)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    members = await group_service.get_members(db, gid)

    # enrich member info
    member_responses = []
    for m in members:
        user = await user_service.get_user_by_id(db, m.user_id)
        mr = GroupMemberResponse.model_validate(m)
        if user:
            mr.username = user.username
            mr.display_name = user.display_name
        member_responses.append(mr)

    resp = GroupDetailResponse.model_validate(group)
    resp.member_count = len(members)
    resp.members = member_responses
    return resp


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: str,
    data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    role = await group_service.get_member_role(db, gid, current_user.id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner or admin can update group")

    group = await group_service.update_group(db, gid, data.name, data.description)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    members = await group_service.get_members(db, gid)
    resp = GroupResponse.model_validate(group)
    resp.member_count = len(members)
    return resp


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    group = await group_service.get_group(db, gid)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    if group.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only creator can delete group")

    await group_service.delete_group(db, gid)


@router.post("/{group_id}/members", status_code=201, response_model=list[GroupMemberResponse])
async def add_members(
    group_id: str,
    data: AddMemberRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    role = await group_service.get_member_role(db, gid, current_user.id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner or admin can add members")

    new_members = await group_service.add_members(db, gid, data.member_ids)
    member_responses = []
    for m in new_members:
        user = await user_service.get_user_by_id(db, m.user_id)
        mr = GroupMemberResponse.model_validate(m)
        if user:
            mr.username = user.username
            mr.display_name = user.display_name
        member_responses.append(mr)
    return member_responses


@router.delete("/{group_id}/members/{user_id}", status_code=204)
async def remove_member(
    group_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID")

    role = await group_service.get_member_role(db, gid, current_user.id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owner or admin can remove members")

    # Cannot remove owner
    group = await group_service.get_group(db, gid)
    if group and uid == group.creator_id:
        raise HTTPException(status_code=403, detail="Cannot remove group owner")

    success = await group_service.remove_member(db, gid, uid)
    if not success:
        raise HTTPException(status_code=404, detail="Member not found")


@router.get("/{group_id}/members", response_model=list[GroupMemberResponse])
async def list_members(
    group_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    members = await group_service.get_members(db, gid)
    member_responses = []
    for m in members:
        user = await user_service.get_user_by_id(db, m.user_id)
        mr = GroupMemberResponse.model_validate(m)
        if user:
            mr.username = user.username
            mr.display_name = user.display_name
        member_responses.append(mr)
    return member_responses


@router.get("/{group_id}/messages", response_model=list[MessageResponse])
async def get_group_messages(
    group_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    try:
        gid = uuid.UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid group ID")

    messages, total = await group_service.get_group_messages(db, gid, page, page_size)
    items = []
    for m in reversed(messages):
        resp = MessageResponse.model_validate(m)
        sender = await user_service.get_user_by_id(db, m.sender_id)
        if sender:
            resp.sender_username = sender.username
            resp.sender_display_name = sender.display_name
        items.append(resp)
    return items
