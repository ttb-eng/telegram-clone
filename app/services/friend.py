import uuid

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friend import Friend, FriendStatus
from app.models.user import User


async def send_friend_request(
    db: AsyncSession, requester: User, addressee: User
) -> Friend:
    existing = await get_friendship(db, requester.id, addressee.id)
    if existing:
        if existing.status == FriendStatus.BLOCKED:
            raise ValueError("Unable to send friend request")
        if existing.status == FriendStatus.PENDING:
            raise ValueError("Friend request already sent")
        if existing.status == FriendStatus.ACCEPTED:
            raise ValueError("Already friends")

        if existing.status == FriendStatus.ACCEPTED:
            raise ValueError("Already friends")

    relation = Friend(requester_id=requester.id, addressee_id=addressee.id)
    db.add(relation)
    await db.commit()
    await db.refresh(relation)
    return relation


async def accept_friend_request(db: AsyncSession, friend_id: uuid.UUID) -> Friend:
    result = await db.execute(
        select(Friend).where(Friend.id == friend_id, Friend.status == FriendStatus.PENDING)
    )
    relation = result.scalar_one_or_none()
    if not relation:
        raise ValueError("Friend request not found or already processed")

    relation.status = FriendStatus.ACCEPTED
    await db.commit()
    await db.refresh(relation)
    return relation


async def reject_friend_request(db: AsyncSession, friend_id: uuid.UUID):
    result = await db.execute(
        select(Friend).where(Friend.id == friend_id, Friend.status == FriendStatus.PENDING)
    )
    relation = result.scalar_one_or_none()
    if not relation:
        raise ValueError("Friend request not found")
    await db.delete(relation)
    await db.commit()


async def get_friendship(
    db: AsyncSession, user_a: uuid.UUID, user_b: uuid.UUID
) -> Friend | None:
    result = await db.execute(
        select(Friend).where(
            or_(
                (Friend.requester_id == user_a) & (Friend.addressee_id == user_b),
                (Friend.requester_id == user_b) & (Friend.addressee_id == user_a),
            )
        )
    )
    return result.scalar_one_or_none()


async def get_friends(db: AsyncSession, user_id: uuid.UUID) -> list[tuple[User, Friend]]:
    stmt = select(Friend).where(
        or_(Friend.requester_id == user_id, Friend.addressee_id == user_id),
        Friend.status == FriendStatus.ACCEPTED,
    )
    result = await db.execute(stmt)
    relations = list(result.scalars().all())

    friends = []
    for rel in relations:
        friend_id = rel.addressee_id if rel.requester_id == user_id else rel.requester_id
        fr_result = await db.execute(select(User).where(User.id == friend_id))
        friend_user = fr_result.scalar_one()
        friends.append((friend_user, rel))
    return friends


async def delete_friend(db: AsyncSession, user_id: uuid.UUID, friend_id: uuid.UUID):
    rel = await get_friendship(db, user_id, friend_id)
    if not rel or rel.status != FriendStatus.ACCEPTED:
        raise ValueError("Friendship not found")
    await db.delete(rel)
    await db.commit()


async def get_pending_requests(
    db: AsyncSession, user_id: uuid.UUID
) -> list[Friend]:
    result = await db.execute(
        select(Friend).where(
            Friend.addressee_id == user_id, Friend.status == FriendStatus.PENDING
        )
    )
    return list(result.scalars().all())
