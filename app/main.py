import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import uuid
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import init_db, close_db, get_db
from app.redis_client import close_redis, get_redis
from app.api import auth, users, friends, messages, upload, groups, ai
from app.api.deps import require_user
from app.models.user import User
from app.config import settings as app_settings
from app.ws.manager import handle_websocket, manager
from app.services.message import mark_messages_read

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")
    await init_db()
    await manager.start_listener()
    yield
    logger.info("Shutting down...")
    await manager.stop_listener()
    await close_db()
    await close_redis()


app = FastAPI(title="Telegram Clone API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(friends.router)
app.include_router(messages.router)
app.include_router(messages.conversations_router)
app.include_router(upload.router)
app.include_router(groups.router)
app.include_router(ai.router)

os.makedirs(app_settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=app_settings.upload_dir), name="uploads")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/offline-messages")
async def get_offline_messages(
    current_user: User = Depends(require_user),
):
    redis_conn = await get_redis()
    raw_messages = await redis_conn.lrange(f"offline_messages:{current_user.id}", 0, -1)
    await redis_conn.delete(f"offline_messages:{current_user.id}")
    messages_list = []
    for raw in raw_messages:
        try:
            messages_list.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return {"messages": messages_list}


@app.get("/api/online/{user_id}")
async def check_online(
    user_id: str,
    current_user: User = Depends(require_user),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    online = await manager.get_online_status(uid)
    return {"user_id": user_id, "online": online}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await handle_websocket(websocket)


# 前端演示页挂在最后：Mount("/") 会匹配一切路径，注册早了会把上面 /api 和 /ws 全遮住
app.mount(
    "/",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True),
    name="frontend",
)


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, workers=4)
