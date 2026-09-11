import asyncio
import json
import uuid
import logging
from collections import defaultdict

import redis.asyncio as redis
from fastapi import WebSocket

from app.services.auth import decode_access_token
from app.redis_client import get_redis
from app.config import settings

logger = logging.getLogger(__name__)

PUBSUB_CHANNEL = "ws:events"


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[uuid.UUID, list[WebSocket]] = defaultdict(list)
        self._pubsub_client = None
        self._pubsub = None
        self._listener_task = None

    async def connect(self, user_id: uuid.UUID, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id].append(websocket)
        await self._set_online(user_id, True)

    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocket):
        ws_list = self.active_connections.get(user_id, [])
        if websocket in ws_list:
            ws_list.remove(websocket)
        if not self.active_connections.get(user_id):
            self.active_connections.pop(user_id, None)
            await self._set_online(user_id, False)

    async def _send_local(self, user_id: uuid.UUID, message: dict):
        for ws in self.active_connections.get(user_id, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    async def send_personal(self, user_id: uuid.UUID, message: dict):
        # 发布到 Redis，各 worker（含本 worker）的 listener 收到后投递给本地连接，
        # 从而保证不同 worker 上的连接也能互相收发消息。
        try:
            redis_conn = await get_redis()
            await redis_conn.publish(
                PUBSUB_CHANNEL,
                json.dumps({"target": str(user_id), "message": message}, default=str),
            )
        except Exception as e:
            logger.warning(f"Redis publish failed, fallback to local: {e}")
            await self._send_local(user_id, message)

    async def broadcast_to_user(self, user_id: uuid.UUID, message: dict):
        await self.send_personal(user_id, message)

    async def start_listener(self):
        try:
            self._pubsub_client = redis.from_url(settings.redis_url, decode_responses=True)
            self._pubsub = self._pubsub_client.pubsub()
            await self._pubsub.subscribe(PUBSUB_CHANNEL)
            self._listener_task = asyncio.create_task(self._listen())
        except Exception as e:
            logger.warning(f"Failed to start pubsub listener: {e}")
            await self.stop_listener()

    async def _listen(self):
        try:
            async for event in self._pubsub.listen():
                if event.get("type") != "message":
                    continue
                try:
                    data = json.loads(event["data"])
                    target = uuid.UUID(data["target"])
                    message = data["message"]
                except (ValueError, KeyError, TypeError):
                    continue
                await self._send_local(target, message)
        except Exception as e:
            logger.warning(f"pubsub listener stopped: {e}")

    async def stop_listener(self):
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe(PUBSUB_CHANNEL)
            except Exception:
                pass
            self._pubsub = None
        if self._pubsub_client:
            try:
                await self._pubsub_client.aclose()
            except Exception:
                pass
            self._pubsub_client = None

    async def send_group(self, group_id: uuid.UUID, message: dict, exclude_user_id: uuid.UUID | None = None):
        from app.redis_client import get_redis
        try:
            redis_conn = await get_redis()
            pattern = f"user:online:*"
            keys = await redis_conn.keys(pattern)
            online_users = set()
            for k in keys:
                uid_str = k.split(":")[-1]
                online_users.add(uuid.UUID(uid_str))
        except Exception:
            online_users = set()

        # Send to group members who are online
        from app.database import async_session_factory
        from app.services.group import get_group_member_ids
        async with async_session_factory() as session:
            member_ids = await get_group_member_ids(session, group_id)
            for mid in member_ids:
                if exclude_user_id and mid == exclude_user_id:
                    continue
                if mid in online_users:
                    await self.send_personal(mid, message)

    async def _set_online(self, user_id: uuid.UUID, online: bool):
        try:
            redis_conn = await get_redis()
            key = f"user:online:{user_id}"
            if online:
                await redis_conn.set(key, "1", ex=300)
            else:
                await redis_conn.delete(key)
        except Exception as e:
            logger.warning(f"Redis error: {e}")

    async def get_online_status(self, user_id: uuid.UUID) -> bool:
        try:
            redis_conn = await get_redis()
            return await redis_conn.exists(f"user:online:{user_id}")
        except Exception:
            return False


manager = ConnectionManager()


async def handle_websocket(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    user_id = decode_access_token(token)
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await manager.connect(user_id, websocket)
    logger.info(f"User {user_id} connected via WebSocket")

    try:
        while True:
            raw = await websocket.receive_json()
            msg_type = raw.get("type")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                # 心跳只负责给在线状态续期，Redis 不可用时不该把连接带崩：
                # 这里的异常会一路抛到下面的 except，finally 里 disconnect 就断线了。
                try:
                    redis_conn = await get_redis()
                    await redis_conn.expire(f"user:online:{user_id}", 120)
                except Exception:
                    pass
                continue

            if msg_type == "message":
                payload = raw.get("payload", {})
                receiver_str = payload.get("receiver_id")
                group_str = payload.get("group_id")
                content = payload.get("content", "")
                msg_id = raw.get("msg_id", str(uuid.uuid4()))

                from app.database import async_session_factory
                from sqlalchemy import select
                from app.models.user import User

                async with async_session_factory() as session:
                    sender_result = await session.execute(select(User).where(User.id == user_id))
                    sender_user = sender_result.scalar_one_or_none()
                    if not sender_user:
                        continue

                    # Group message
                    if group_str:
                        group_uuid = uuid.UUID(group_str)
                        from app.services.message import create_group_message
                        msg = await create_group_message(session, sender_user, group_uuid, content, "text")

                        msg_payload = {
                            "type": "new_message",
                            "payload": {
                                "msg_id": str(msg.id),
                                "sender_id": str(user_id),
                                "group_id": group_str,
                                "content": content,
                                "sender_username": sender_user.username,
                                "sender_display_name": sender_user.display_name,
                                "created_at": msg.created_at.isoformat(),
                            },
                        }

                        await manager.send_group(group_uuid, msg_payload, exclude_user_id=user_id)

                        await websocket.send_json({
                            "type": "message_ack",
                            "payload": {"msg_id": msg_id, "status": "delivered"},
                        })
                        continue

                    # Private message
                    receiver_uuid = uuid.UUID(receiver_str) if receiver_str else None
                    if receiver_uuid:
                        from app.redis_client import get_redis
                        receiver_result = await session.execute(select(User).where(User.id == receiver_uuid))
                        receiver_user = receiver_result.scalar_one_or_none()

                        if sender_user and receiver_user:
                            from app.services.message import create_message
                            await create_message(session, sender_user, receiver_user, content, "text")

                            if receiver_user.username == 'ai_bot':
                                from app.config import settings
                                from app.services.message import get_recent_context

                                recent_msgs = await get_recent_context(
                                    session, sender_user.id, receiver_user.id
                                )

                                context_messages = [
                                    {"role": "system", "content": "你是一个乐于助人的AI助手，回答简洁准确。请使用中文回复。"}
                                ]
                                for msg in recent_msgs:
                                    role = "user" if msg.sender_id == sender_user.id else "assistant"
                                    context_messages.append({"role": role, "content": msg.content})

                                if settings.use_langchain_agent:
                                    from app.services.langchain_bot import get_ai_reply_langchain
                                    get_reply = get_ai_reply_langchain
                                else:
                                    from app.services.deepseek import get_ai_reply_with_tools
                                    get_reply = get_ai_reply_with_tools

                                # 真流式：每来一块就推一条 ai_stream，前端按 stream_id 归到同一个气泡；
                                # 生成完整内容后再落库，最后推 ai_done 定稿（带真实 msg_id）。
                                # 之所以能推给自己，是因为 send_personal 走 Redis pub/sub 回环，
                                # 不像 send_group 那样排除发送者。
                                stream_id = str(uuid.uuid4())
                                full_reply = ""
                                async for chunk in get_reply(context_messages, str(sender_user.id)):
                                    full_reply += chunk
                                    await manager.send_personal(sender_user.id, {
                                        "type": "ai_stream",
                                        "payload": {
                                            "stream_id": stream_id,
                                            "sender_id": str(receiver_user.id),
                                            "delta": chunk,
                                        },
                                    })

                                ai_msg_row = await create_message(
                                    session, receiver_user, sender_user, full_reply, "text"
                                )
                                await manager.send_personal(sender_user.id, {
                                    "type": "ai_done",
                                    "payload": {
                                        "stream_id": stream_id,
                                        "msg_id": str(ai_msg_row.id),
                                        "sender_id": str(receiver_user.id),
                                        "receiver_id": str(sender_user.id),
                                        "content": full_reply,
                                        "created_at": ai_msg_row.created_at.isoformat(),
                                    },
                                })

                        msg_payload = {
                            "type": "new_message",
                            "payload": {
                                "msg_id": msg_id,
                                "sender_id": str(user_id),
                                "receiver_id": receiver_str,
                                "content": content,
                                "created_at": __import__("datetime").datetime.now().isoformat(),
                            },
                        }

                        online = await manager.get_online_status(receiver_uuid)
                        if online:
                            await manager.send_personal(receiver_uuid, msg_payload)
                        else:
                            try:
                                redis_conn = await get_redis()
                                await redis_conn.lpush(
                                    f"offline_messages:{receiver_uuid}",
                                    json.dumps(msg_payload, default=str),
                                )
                                await redis_conn.ltrim(f"offline_messages:{receiver_uuid}", 0, 999)
                            except Exception as e:
                                logger.warning(f"Failed to store offline message: {e}")

                        await websocket.send_json({
                            "type": "message_ack",
                            "payload": {"msg_id": msg_id, "status": "delivered"},
                        })

            elif msg_type == "typing":
                receiver_str = raw.get("receiver_id")
                if receiver_str:
                    await manager.send_personal(
                        uuid.UUID(receiver_str),
                        {"type": "typing", "sender_id": str(user_id)},)


    except Exception as e:
        logger.info(f"WebSocket disconnected for user {user_id}: {e}")
    finally:
        await manager.disconnect(user_id, websocket)
