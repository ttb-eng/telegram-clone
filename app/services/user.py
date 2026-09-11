from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserRegister, UserUpdate
from app.services.auth import hash_password


async def create_user(db: AsyncSession, data: UserRegister) -> User:
    user = User(
        phone=data.phone,
        username=data.username,
        display_name=data.display_name,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_user_by_phone(db: AsyncSession, phone: str) -> User | None:
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()

# select(User).where(User.phone == phone) 构造 SQL：SELECT * FROM users WHERE phone = ?
#
# scalar_one_or_none()：返回单个用户，如果没有找到则返回 None，如果多于一个（理论上不会）会抛出异常。

async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user


# 接收一个已存在的 User 对象（通常先从数据库查出来）和 UserUpdate schema。
# data.model_dump(exclude_none=True)：将 Pydantic 模型转为字典，排除值为 None 的字段（这样只更新客户端传递的字段）。
# 遍历字典，用 setattr 动态设置对象的属性。
# commit() 保存更改，refresh() 重新加载（确保返回最新数据）。


async def search_users(db: AsyncSession, query: str, limit: int = 20) -> list[User]:
    stmt = (
        select(User)
        .where(
            User.username.ilike(f"%{query}%") | User.display_name.ilike(f"%{query}%")
        )
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def delete_user(db: AsyncSession, user: User) -> User | None:
    await db.delete(user)
    await db.commit()


async def create_ai_bot_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.username == "ai_bot"))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    from app.services.auth import hash_password
    bot = User(
        phone="+00000000000",
        username="ai_bot",
        display_name="AI 助手",
        hashed_password=hash_password("dummy-password-not-for-login"),
        bio="我是 AI 助手，基于 DeepSeek 构建",
        avatar_url=None,
    )
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    return bot


# ilike 是大小写不敏感的模糊匹配（相当于 SQL 的 ILIKE）。
#
# 条件：username 或 display_name 包含查询字符串。
#
# limit(limit) 限制返回结果数（默认 20）。
#
# result.scalars().all()：获取所有匹配的用户对象，转为列表返回。