import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.group import Group, GroupMember, GroupRole
from app.models.user import User
from app.models.message import Message


async def create_group(
    db: AsyncSession, creator: User, name: str, description: str | None = None,
    member_ids: list[uuid.UUID] | None = None,
) -> Group:
    group = Group(
        name=name,
        description=description,
        creator_id=creator.id,
    )
    db.add(group)
    await db.flush()

    # creator is owner
    owner = GroupMember(group_id=group.id, user_id=creator.id, role=GroupRole.OWNER)
    db.add(owner)

    # add extra members
    added_ids = {creator.id}
    if member_ids:
        for mid in member_ids:
            if mid not in added_ids:
                db.add(GroupMember(group_id=group.id, user_id=mid, role=GroupRole.MEMBER))
                added_ids.add(mid)

    await db.commit()
    await db.refresh(group)
    return group


async def get_group(db: AsyncSession, group_id: uuid.UUID) -> Group | None:
    result = await db.execute(
        select(Group).options(joinedload(Group.members)).where(Group.id == group_id)
    )
    return result.unique().scalar_one_or_none()


async def get_user_groups(db: AsyncSession, user_id: uuid.UUID) -> list[Group]:
    result = await db.execute(
        select(Group).where(
            Group.id.in_(
                select(GroupMember.group_id).where(GroupMember.user_id == user_id)
            )
        ).order_by(desc(Group.updated_at))
    )
    return list(result.scalars().all())


async def update_group(
    db: AsyncSession, group_id: uuid.UUID, name: str | None = None,
    description: str | None = None,
) -> Group | None:
    group = await get_group(db, group_id)
    if not group:
        return None
    if name is not None:
        group.name = name
    if description is not None:
        group.description = description
    await db.commit()
    await db.refresh(group)
    return group


async def delete_group(db: AsyncSession, group_id: uuid.UUID) -> bool:
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        return False
    await db.delete(group)
    await db.commit()
    return True


async def add_members(
    db: AsyncSession, group_id: uuid.UUID, member_ids: list[uuid.UUID],
) -> list[GroupMember]:
    existing = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id.in_(member_ids),
        )
    )
    existing_ids = {m.user_id for m in existing.scalars().all()}

    new_members = []
    for uid in member_ids:
        if uid not in existing_ids:
            member = GroupMember(group_id=group_id, user_id=uid, role=GroupRole.MEMBER)
            db.add(member)
            new_members.append(member)

    if new_members:
        await db.commit()
        for m in new_members:
            await db.refresh(m)
    return new_members


async def remove_member(db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        return False
    await db.delete(member)
    await db.commit()
    return True


async def get_members(db: AsyncSession, group_id: uuid.UUID) -> list[GroupMember]:
    result = await db.execute(
        select(GroupMember)
        .where(GroupMember.group_id == group_id)
        .order_by(GroupMember.joined_at)
    )
    return list(result.scalars().all())


async def get_member_role(
    db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID
) -> GroupRole | None:
    result = await db.execute(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    return member.role if member else None


async def get_group_member_ids(db: AsyncSession, group_id: uuid.UUID) -> list[uuid.UUID]:
    result = await db.execute(
        select(GroupMember.user_id).where(GroupMember.group_id == group_id)
    )
    return list(result.scalars().all())


async def get_group_last_message(
    db: AsyncSession, group_id: uuid.UUID,
) -> Message | None:
    result = await db.execute(
        select(Message)
        .where(Message.group_id == group_id, Message.is_recalled == False)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_group_unread_count(
    db: AsyncSession, group_id: uuid.UUID, user_id: uuid.UUID, after: datetime | None = None,
) -> int:
    stmt = select(func.count()).where(
        Message.group_id == group_id,
        Message.sender_id != user_id,
        Message.is_recalled == False,
    )
    if after:
        stmt = stmt.where(Message.created_at > after)
    result = await db.execute(stmt)
    return result.scalar()


async def get_group_messages(
    db: AsyncSession, group_id: uuid.UUID, page: int = 1, page_size: int = 50,
) -> tuple[list[Message], int]:
    stmt = (
        select(Message)
        .where(Message.group_id == group_id)
        .order_by(desc(Message.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    messages = list(result.scalars().all())

    count_stmt = select(func.count()).where(Message.group_id == group_id)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()
    return messages, total
