import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.friend import FriendStatus


class FriendRequest(BaseModel):
    username: str


class FriendResponse(BaseModel):
    id: uuid.UUID
    friend_id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None = None
    status: FriendStatus
    created_at: datetime


class FriendRequestResponse(BaseModel):
    id: uuid.UUID
    requester_id: uuid.UUID
    requester_username: str
    requester_display_name: str
    status: FriendStatus
    created_at: datetime
