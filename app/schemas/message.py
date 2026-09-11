import uuid
from datetime import datetime

from pydantic import BaseModel


class MessageSend(BaseModel):
    receiver_username: str | None = None
    group_id: str | None = None
    content: str
    msg_type: str = "text"


class MessageResponse(BaseModel):
    id: uuid.UUID
    sender_id: uuid.UUID
    receiver_id: uuid.UUID | None = None
    group_id: uuid.UUID | None = None
    sender_username: str = ""
    sender_display_name: str = ""
    content: str
    msg_type: str
    is_read: bool
    read_at: datetime | None = None
    is_recalled: bool = False
    recalled_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationPreview(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None = None
    last_message: str
    last_message_time: datetime
    unread_count: int


class GroupConversationPreview(BaseModel):
    group_id: uuid.UUID
    group_name: str
    last_message: str
    last_message_time: datetime
    unread_count: int
    member_count: int


class ReadReceiptResponse(BaseModel):
    message_ids: list[uuid.UUID]
