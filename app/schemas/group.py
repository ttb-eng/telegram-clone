import uuid
from datetime import datetime

from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    member_ids: list[uuid.UUID] = []


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class GroupMemberResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    username: str = ""
    display_name: str = ""
    role: str
    joined_at: datetime

    model_config = {"from_attributes": True}


class GroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    avatar_url: str | None = None
    creator_id: uuid.UUID
    member_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GroupDetailResponse(GroupResponse):
    members: list[GroupMemberResponse] = []


class AddMemberRequest(BaseModel):
    member_ids: list[uuid.UUID]
