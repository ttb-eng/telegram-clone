# Telegram Clone API

仿 Telegram 的实时通讯 API，基于 **FastAPI + PostgreSQL + Redis + WebSocket + AI** 构建。

> 在线演示：https://mytelegram.xyz/docs （Swagger UI）

---

## 项目亮点

| 亮点 | 说明 |
|------|------|
| AI Bot + 连续对话 | 集成 DeepSeek API，支持多轮上下文记忆 |
| Tool Calling | AI 可调用工具：查时间 / 查天气 / 联网搜索 / 文档知识库 |
| **AI 流式输出** | 两条链路都是真流式：WebSocket 增量帧（`ai_stream` / `ai_done`）+ RAG 问答 NDJSON |
| RAG 文档问答 | ChromaDB + sentence-transformers，上传文档后 AI 基于文档回答 |
| WebSocket 实时通信 | 消息推送、在线状态、输入状态、离线消息队列 |
| 群聊系统 | 创建群组、成员管理、消息多播广播 |
| 单文件前端 | `app/static/index.html`，原生 JS 无框架；开两个标签页可各登一个账号（登录态在 `sessionStorage`） |
| 异步架构 | FastAPI + SQLAlchemy Async + asyncpg 全异步链路 |
| 部署上线 | 云服务器 + systemd + Nginx 反代 + PostgreSQL |

## 技术栈

| 技术 | 用途 |
|------|------|
| **FastAPI** | Web 框架 |
| **SQLAlchemy** (Async) | ORM + asyncpg 驱动 |
| **PostgreSQL** | 生产数据库 |
| **Redis** | 缓存 + 在线状态 + 离线队列 |
| **WebSocket** | 实时消息推送 |
| **JWT** (python-jose) | 用户认证 |
| **bcrypt** (passlib) | 密码哈希 |
| **DeepSeek API** | AI 对话引擎 |
| **ChromaDB** | 向量数据库（文档检索） |
| **sentence-transformers** | 文本向量化（Embedding） |
| **PyPDF2** | PDF 文件解析 |
| **原生 JavaScript** | 演示前端（单文件 SPA，无框架、无构建） |
| **Nginx** | 反向代理 |
| **systemd** | 进程守护 + 开机自启 |
| **Docker** | 容器化部署 |

## 项目结构

```
telegram-clone/
├── app/
│   ├── main.py              # 应用入口，路由注册 & CORS
│   ├── config.py            # 配置管理（环境变量）
│   ├── database.py          # 异步 SQLAlchemy 引擎 & 会话
│   ├── redis_client.py      # Redis 异步客户端
│   ├── models/              # SQLAlchemy ORM 模型
│   │   ├── user.py
│   │   ├── friend.py
│   │   ├── message.py
│   │   ├── group.py
│   │   └── document.py      # 文档元数据
│   ├── schemas/             # Pydantic 请求/响应模型
│   │   ├── user.py
│   │   ├── friend.py
│   │   ├── message.py
│   │   └── group.py
│   ├── api/                 # HTTP API 路由
│   │   ├── auth.py          # 注册/登录
│   │   ├── users.py         # 用户信息
│   │   ├── friends.py       # 好友管理
│   │   ├── messages.py      # 消息发送/历史/搜索/撤回
│   │   ├── groups.py        # 群组管理
│   │   ├── upload.py        # 文件上传
│   │   └── ai.py            # RAG 文档上传/搜索/问答
│   ├── services/            # 业务逻辑层
│   │   ├── auth.py          # JWT 签发 & 验证
│   │   ├── user.py
│   │   ├── friend.py
│   │   ├── message.py       # 含 AI 连续对话上下文
│   │   ├── group.py         # 群组业务逻辑
│   │   ├── deepseek.py      # DeepSeek AI 流式回复 + Tool Calling
│   │   ├── rag.py           # RAG 文档向量化+检索
│   │   └── tools.py         # Tool Calling 工具定义
│   ├── ws/
│   │   └── manager.py       # WebSocket 连接管理（含 AI 流式增量推送）
│   └── static/
│       └── index.html       # 演示前端（单文件 SPA，原生 JS）
├── tests/                   # pytest 测试
├── docs/                    # RAG 评测报告
├── uploads/                 # 上传文件目录
├── chroma_data/             # ChromaDB 向量数据
├── start_demo.bat           # Windows 本地演示一键启动（Redis + 后端）
├── docker-compose.yml       # 一键部署
├── Dockerfile
├── requirements.txt
└── .env                     # 环境变量配置
```

## 快速启动

### 本地演示（Windows，一条命令）

```
start_demo.bat
```

脚本自动完成三件事：检测并拉起 Redis（原生 Windows 版，**不需要管理员权限、不需要 Docker、不需要虚拟化**）→ 清空环境里那个指向不存在文件的 `SSL_CERT_FILE` → 用单 worker 启动后端。

- **演示页面**（前端 SPA）：http://127.0.0.1:8000
- Swagger 文档：http://127.0.0.1:8000/docs
- 演示账号：`13900000001` / `demo123456`、`13900000002` / `demo123456`
- **双窗口演示**：开两个标签页分别登录即可（登录态存 `sessionStorage` 而不是 `localStorage`，两个标签页互不干扰）
- **启动窗口不要关**：AI 的 Tool Calling 调用日志（`AI调用了：get_weather({'city': '北京'})`）会打印在那里

> 注意：`start_demo.bat` 必须保持 **GBK 编码 + CRLF 换行**，否则 cmd 会把每行拆成命令执行；脚本里也不要加 `chcp 65001`，那会让 cmd 的解析指针错位。

### 方式一：本地开发

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动 PostgreSQL 和 Redis（需 Docker）
docker compose up db redis -d

# 3. 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

### 方式二：Docker 一键部署

```bash
docker compose up -d --build
```

### 方式三：生产部署

```bash
# systemd 进程管理
systemctl start telegram-clone
systemctl enable telegram-clone    # 开机自启
systemctl status telegram-clone     # 查看状态
```

---

## API 接口

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册（phone, username, display_name, password） |
| POST | `/api/auth/login` | 登录（phone, password） |

### 用户

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/users/me` | 获取当前用户信息 |
| PATCH | `/api/users/me` | 更新个人信息 |
| DELETE | `/api/users/me` | 注销当前账号 |
| GET | `/api/users/search?q=` | 搜索用户 |
| GET | `/api/users/{id}` | 获取指定用户信息 |
| DELETE | `/api/users/{id}` | 删除指定用户 |

### 好友

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/friends/requests` | 发送好友请求 |
| POST | `/api/friends/requests/{id}/accept` | 接受好友请求 |
| POST | `/api/friends/requests/{id}/reject` | 拒绝好友请求 |
| GET | `/api/friends/requests` | 查看收到的好友请求 |
| DELETE | `/api/friends/{id}` | 删除好友 |
| GET | `/api/friends` | 好友列表 |

> 注意：`requests/{id}/accept|reject` 里的 `{id}` 是**好友关系记录的 id**（`POST /requests` 返回的那个 `id`），不是对方的用户 id；`DELETE /friends/{id}` 里的 `{id}` 才是用户 id。

### 消息

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/messages` | 发送消息（REST 备用通道） |
| GET | `/api/messages/{peer_id}?page=1&page_size=50` | 聊天历史（分页） |
| POST | `/api/messages/read/{peer_id}` | 标记已读 |
| POST | `/api/messages/{msg_id}/recall` | 撤回消息（只能撤自己的，超时/非本人返回 400） |
| GET | `/api/messages/search/all?q=&page=1&page_size=50` | 搜索消息 |
| GET | `/api/conversations` | 会话列表（私聊+群聊） |

### 群聊

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/groups` | 创建群组 |
| GET | `/api/groups` | 我的群组列表 |
| GET | `/api/groups/{id}` | 群组详情 |
| PATCH | `/api/groups/{id}` | 修改群信息（群主/管理员） |
| DELETE | `/api/groups/{id}` | 解散群组（群主） |
| POST | `/api/groups/{id}/members` | 添加成员 |
| DELETE | `/api/groups/{id}/members/{uid}` | 移除成员 |
| GET | `/api/groups/{id}/members` | 成员列表 |
| GET | `/api/groups/{id}/messages` | 群消息历史（分页） |

### 文件上传

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload` | 上传文件（类型/大小校验） |

### RAG 文档问答

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ai/documents` | 上传文档（支持 TXT/PDF） |
| GET | `/api/ai/documents` | 我的文档列表 |
| DELETE | `/api/ai/documents/{id}` | 删除文档 |
| POST | `/api/ai/rag-query` | 基于文档的 RAG 问答（**NDJSON 流式响应**） |

数据流：上传 → 分块(500字/50重叠) → sentence-transformers 向量化(384维) → ChromaDB 存储 → 用户提问 → 向量检索(余弦相似度 top5) → 拼上下文 → DeepSeek 生成回答

**`/api/ai/rag-query` 的响应是流式的**（`Content-Type: application/x-ndjson`），一行一个 JSON 事件：

```
{"type": "sources", "sources": [{"filename": "spec.txt", "snippet": "……", "distance": 0.6732}]}
{"type": "delta", "text": "星河"}
{"type": "delta", "text": "项目的"}
{"type": "done"}
```

顺序固定：`sources` 先到（检索结果，含文件名 / 片段 / 余弦距离）→ 若干 `delta` 增量 → `done` 收尾。前端因此用 `fetch` + `response.body.getReader()` 边收边渲染，而不是等整个响应体回来。

两个实现细节：

- 检索事件之所以排在 `delta` 之前，是因为 embedding + ChromaDB 查询是同步做完的；**真正的模型生成在它之后才开始**。所以文档上下文较长时，**第一个 `delta` 可能要等十几秒**（实测 2 个 chunk 约 14s），这段时间前端一直显示"正在检索文档…"，不是卡死。
- 后端用 `json.dumps` 的默认 `ensure_ascii=True`：正文里的换行会被转义，所以每条事件天然占一行，前端按行切分即可。

### 实时

| 协议 | 路径 | 说明 |
|------|------|------|
| WebSocket | `/ws?token={jwt}` | 实时消息连接 |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/offline-messages` | 拉取离线消息 |
| GET | `/api/online/{user_id}` | 查询用户在线状态 |
| GET | `/api/health` | 健康检查 |
| WebSocket | `/ws?token={jwt}` | 实时消息（私聊+群聊） |

---

## AI Bot

项目内置一个 AI Bot 用户（`ai_bot`），启动时自动创建。发送消息给 `ai_bot` 即可触发 DeepSeek AI 自动回复。

回复是**流式**的：WebSocket 先推若干 `ai_stream` 增量帧，生成完成后再推一条 `ai_done` 定稿（格式见上文「WebSocket 消息格式」）。注意**工具调用那一轮不是流式的**——要先拿到完整响应才能看出模型要不要调工具，只有最后一轮生成正文时才有增量。

### 连续对话

AI 能记住最近 **20 条** 历史消息作为上下文，实现连贯的多轮对话。

### Tool Calling（函数调用）

AI 可以调用以下工具：

| 工具 | 说明 | 示例 |
|------|------|------|
| `get_time` | 查询指定时区的当前时间 | "现在几点？" |
| `get_weather` | 查询城市天气 | "北京天气怎么样？" |
| `web_search` | 联网搜索最新信息（Tavily API） | "今天有什么新闻？" |
| `search_knowledge` | 检索用户上传的文档知识库 | "我文档里提到了什么？" |

配置方式：在 `.env` 中填入 DeepSeek API Key：

```
DEEPSEEK_API_KEY=sk-your-key-here
```

---

## 部署架构

```
用户浏览器 → Nginx (80端口) → FastAPI (8000) → PostgreSQL + Redis
                                                    ↑
                                              systemd 守护进程
```

- 云服务器：阿里云 ECS（Ubuntu 24.04）
- 进程管理：systemd（开机自启 + 崩溃自动重启）
- 反向代理：Nginx
- 数据库：PostgreSQL（异步 asyncpg）
- 缓存：Redis

## WebSocket 消息格式

**发送消息：**
```json
{
  "type": "message",
  "msg_id": "uuid",
  "payload": {
    "receiver_id": "uuid",
    "content": "Hello!",
    "msg_type": "text"
  }
}
```

（`msg_id` 在顶层；`msg_type` 目前服务端不读，一律按 `text` 落库。私聊的 `payload` 用 `receiver_id`，群聊用 `group_id`。）

**接收消息：**
```json
{
  "type": "new_message",
  "payload": {
    "msg_id": "uuid",
    "sender_id": "uuid",
    "receiver_id": "uuid",
    "content": "Hello!",
    "created_at": "2024-01-01T00:00:00"
  }
}
```

**发送群消息：** 同一个 `message` 类型，把 `receiver_id` 换成 `payload.group_id` 即可：

```json
{
  "type": "message",
  "msg_id": "uuid",
  "payload": {"group_id": "uuid", "content": "Hello group!"}
}
```

**接收群消息：**

```json
{
  "type": "new_message",
  "payload": {
    "msg_id": "uuid",
    "sender_id": "uuid",
    "group_id": "uuid",
    "content": "Hello group!",
    "sender_username": "demo_a",
    "sender_display_name": "演示账号",
    "created_at": "2024-01-01T00:00:00"
  }
}
→ 服务端广播给群内【在线】成员，且【不回显给发送者】（发送者需要自己乐观渲染）
```

> 注意：群消息推送里**没有 `group_name` 字段**。前端若对未知群直接建会话，就只能拿 `sender_display_name` 当群名——所以群名要靠 `GET /api/conversations`（那里返回 `group_name`）来校准。

**AI 流式回复：** 给 `ai_bot` 发消息时，回复不是一次性推过来的，而是先若干帧增量、最后一帧定稿：

```json
{"type": "ai_stream", "payload": {"stream_id": "uuid", "sender_id": "ai_bot-uuid", "delta": "北京"}}
{"type": "ai_done",   "payload": {"stream_id": "uuid", "msg_id": "真实消息id", "sender_id": "ai_bot-uuid",
                                  "receiver_id": "你的uuid", "content": "北京今天多云……", "created_at": "……"}}
```

前端按 `stream_id` 把增量归到同一个气泡，`ai_done` 到达时才用真实 `msg_id` 定稿。之所以要 `stream_id` 而不是直接推全文，是为了支持"流式生成期间切走会话、再切回来"。

**确认与输入状态**（以下都是服务端 → 客户端方向）：

```json
{"type": "message_ack", "payload": {"msg_id": "uuid", "status": "delivered"}}
{"type": "typing", "sender_id": "uuid"}
```

**心跳：** 服务端的在线状态是 Redis 里一个 **300 秒 TTL** 的 key，只靠 ping 续期。客户端需要定期（本项目前端 60 秒一次）发心跳，否则 5 分钟后会被判定为离线，私聊静默进离线队列、群聊谁都收不到。

```json
{"type": "ping"}
→ {"type": "pong"}
```

## 测试

```bash
pytest -v
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT 签名密钥 | (需修改) |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | (可选) |
| `TAVILY_API_KEY` | Tavily 联网搜索 API 密钥 | (可选) |
| `CHROMA_DB_PATH` | ChromaDB 向量数据存储路径 | `./chroma_data` |
| `MAX_UPLOAD_SIZE_MB` | 上传文件大小限制 | 20 |

---


