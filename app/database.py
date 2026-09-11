from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool



# create_async_engine: 创建异步数据库引擎。
# async_sessionmaker: 一个工厂类，用于创建异步会话对象。
# AsyncSession: 异步会话类型，用于执行 ORM 操作。
# DeclarativeBase: 所有模型类的基础类（后面模型会继承它）。
# NullPool: 一种连接池策略，不缓存连接，每次请求都新建一个连接（对 SQLite 和简单场景比较友好，生产环境常用其他池）。




from app.config import settings

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

#导入配置对象，里面包含了 database_url 字符串（如 sqlite+aiosqlite:///./telegram_clone.db）。


engine = create_async_engine(
    settings.database_url,
    echo=False,
    poolclass=NullPool,
    connect_args=connect_args,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# echo=False：不打印每个执行的 SQL 语句（True 用于调试）。
# poolclass=NullPool：使用空连接池（每个请求新建连接，用完即关）。也可以使用 AsyncAdaptedQueuePool 等，但简单项目用 NullPool 足够。
# connect_args：传给底层数据库驱动的额外参数（如上面设置的 check_same_thread）。
#创建会话工厂，后面每次 async_session_factory() 都会生成一个新的 AsyncSession 对象。
# expire_on_commit=False：提交后不使实例过期（避免某些属性需要重新加载）。一般设为 False 更直观。



class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


#  Base — 模型基类。所有数据表模型（User、Message、Friend）都继承它，SQLAlchemy 通过它知道"哪些类是数据表"，init_db()
#   里的 Base.metadata.create_all 就是扫描所有继承 Base 的类来自动建表。
#
#   get_db() — FastAPI 的依赖注入函数，用 async with 包裹，保证会话用完自动关闭：
#
#   调用 async_session_factory() → 创建一个新会话
#     ↓
#   yield session → 把会话交给路由函数使用
#     ↓
#   路由函数执行完 → 回到 finally → session.close() 关闭会话
#
#   async with 就是"结束时自动清理"，try/finally 确保就算路由里抛了异常，会话也会被关闭。
#
#   路由里这样用：
#
#   @app.get("/users")
#   async def get_users(db: AsyncSession = Depends(get_db)):
#       # db 就是 get_db() yield 出来的会话
#       result = await db.execute(...)
#       return result
#
#   每次请求一个会话，用完就关——简单安全。

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Migration: add missing columns to existing tables
    async with engine.begin() as conn:
        def _migrate(sync_conn):
            from sqlalchemy import inspect
            inspector = inspect(sync_conn)
            columns = [c["name"] for c in inspector.get_columns("messages")]
            if "is_recalled" not in columns:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE messages ADD COLUMN is_recalled BOOLEAN DEFAULT 0"
                )
            if "recalled_at" not in columns:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE messages ADD COLUMN recalled_at TIMESTAMP"
                )
            if "group_id" not in columns:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE messages ADD COLUMN group_id UUID"
                )
        await conn.run_sync(_migrate)

    # Create AI Bot user
    from app.services.user import create_ai_bot_user
    async with async_session_factory() as session:
        await create_ai_bot_user(session)

#
# init_db() 在应用启动时被 lifespan 调用，做两件事：
#
#   第一部分 — 建表：
#   engine.begin() → 开启事务
#     ↓
#   conn.run_sync(Base.metadata.create_all) → 扫所有继承 Base 的模型类，在数据库里建表
#                                              如果表已存在，自动跳过（不会覆盖）
#
#   第二部分 — 数据库迁移：
#   engine.begin() → 再开一个事务
#     ↓
#   conn.run_sync(_migrate) → 执行同步函数 _migrate
#     ↓
#   inspect(conn).get_columns("messages") → 查 messages 表当前有哪些列
#     ↓
#   如果缺少 is_recalled 列 → ALTER TABLE 加上（默认 false）
#   如果缺少 recalled_at 列 → ALTER TABLE 加上（时间戳）
#
#   这里有个设计缺陷：这只是"加列"的补丁，只能加新列、不能改或删。正常应该用 Alembic 做迁移管理。

async def close_db():
    await engine.dispose()


#关闭数据库引擎，释放连接池资源。在应用关闭时调用




# 这个文件封装了异步 SQLAlchemy 的配置，提供了：
# 引擎和会话工厂。
# 基类用于定义模型。
# 依赖项 get_db 供路由使用。
# 初始化（建表）和清理函数