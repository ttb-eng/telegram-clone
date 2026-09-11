import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, or_, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.models.user import User


async def create_message(
    db: AsyncSession, sender: User, receiver: User, content: str, msg_type: str = "text"
) -> Message:
    msg = Message(
        sender_id=sender.id,
        receiver_id=receiver.id,
        content=content,
        msg_type=msg_type,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def create_group_message(
    db: AsyncSession, sender: User, group_id: uuid.UUID, content: str, msg_type: str = "text"
) -> Message:
    msg = Message(
        sender_id=sender.id,
        group_id=group_id,
        content=content,
        msg_type=msg_type,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_chat_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    peer_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Message], int]:
    stmt = (
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == user_id, Message.receiver_id == peer_id),
                and_(Message.sender_id == peer_id, Message.receiver_id == user_id),
            )
        )
        .order_by(desc(Message.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    count_stmt = (
        select(func.count())
        .where(
            or_(
                and_(Message.sender_id == user_id, Message.receiver_id == peer_id),
                and_(Message.sender_id == peer_id, Message.receiver_id == user_id),
            )
        )
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    return messages, total


async def mark_messages_read(
    db: AsyncSession, user_id: uuid.UUID, sender_id: uuid.UUID
) -> list[Message]:
    stmt = (
        select(Message)
        .where(
            Message.sender_id == sender_id,
            Message.receiver_id == user_id,
            Message.is_read == False,
        )
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())
    now = datetime.now(timezone.utc)
    for msg in messages:
        msg.is_read = True
        msg.read_at = now
    await db.commit()
    return messages


async def get_unread_count(
    db: AsyncSession, user_id: uuid.UUID, peer_id: uuid.UUID
) -> int:
    stmt = select(func.count()).where(
        Message.sender_id == peer_id,
        Message.receiver_id == user_id,
        Message.is_read == False,
    )
    result = await db.execute(stmt)
    return result.scalar()


async def get_conversations(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[User, Message | None, int]]:
    subq = (
        select(
            Message.receiver_id,
            Message.sender_id,
            func.max(Message.created_at).label("max_time"),
        )
        .where(
            or_(Message.sender_id == user_id, Message.receiver_id == user_id),
            Message.is_recalled == False,
        )
        .group_by(Message.sender_id, Message.receiver_id)
        .subquery()
    )

    last_msgs = (
        select(Message)
        .where(
            or_(
                and_(
                    Message.sender_id == subq.c.sender_id,
                    Message.receiver_id == subq.c.receiver_id,
                    Message.created_at == subq.c.max_time,
                ),
                and_(
                    Message.sender_id == subq.c.receiver_id,
                    Message.receiver_id == subq.c.sender_id,
                    Message.created_at == subq.c.max_time,
                ),
            )
        )
        .distinct()
        .subquery()
    )

    stmt = (
        select(User, last_msgs.c.content, last_msgs.c.created_at)
        .join(last_msgs, or_(
            User.id == last_msgs.c.sender_id,
            User.id == last_msgs.c.receiver_id,
        ))
        .where(User.id != user_id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    conversations = []
    for row in rows:
        peer = row[0]
        last_content = row[1]
        last_time = row[2]
        unread = await get_unread_count(db, user_id, peer.id)
        conversations.append((peer, last_content, last_time, unread))
    return conversations


async def get_recent_context(
    db: AsyncSession,
    user_id: uuid.UUID,
    peer_id: uuid.UUID,
    limit: int = 20,
) -> list[Message]:
    """获取两个用户之间的最近 N 条消息，按时间正序，用于 AI 上下文。"""
    stmt = (
        select(Message)
        .where(
            or_(
                and_(Message.sender_id == user_id, Message.receiver_id == peer_id),
                and_(Message.sender_id == peer_id, Message.receiver_id == user_id),
            )
        )
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())
    messages.reverse()  # 转为正序（旧→新）
    return messages


async def recall_message(
    db: AsyncSession, message_id: uuid.UUID, user_id: uuid.UUID
) -> Message:
    result = await db.execute(select(Message).where(Message.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        raise ValueError("Message not found")
    if msg.sender_id != user_id:
        raise ValueError("You can only recall your own messages")
    if msg.is_recalled:
        raise ValueError("Message already recalled")

    now = datetime.now(timezone.utc)
    # handle naive/aware datetime from SQLite
    created = msg.created_at
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = (now - created).total_seconds()

    if delta > 120:
        raise ValueError("Message can only be recalled within 2 minutes")

    msg.is_recalled = True
    msg.recalled_at = now
    msg.content = "[消息已被撤回]"
    await db.commit()
    await db.refresh(msg)
    return msg


async def search_messages(
    db: AsyncSession,
    user_id: uuid.UUID,
    query: str,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Message], int]:
    stmt = (
        select(Message)
        .where(
            and_(
                or_(
                    Message.sender_id == user_id,
                    Message.receiver_id == user_id,
                ),
                Message.content.ilike(f"%{query}%"),
                Message.is_recalled == False,
            )
        )
        .order_by(desc(Message.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    count_stmt = (
        select(func.count())
        .where(
            and_(
                or_(
                    Message.sender_id == user_id,
                    Message.receiver_id == user_id,
                ),
                Message.content.ilike(f"%{query}%"),
                Message.is_recalled == False,
            )
        )
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()
    return messages, total
