"""
WebSocket 性能压测脚本
用法：
  1. 先启动服务器：uvicorn app.main:app --host 127.0.0.1 --port 8000
  2. 运行压测：python tests/ws_bench.py
  3. 可选参数：python tests/ws_bench.py --clients 500 --duration 30
"""

import asyncio
import json
import os
import sys
import time
import uuid
import argparse
from dataclasses import dataclass, field

import httpx
import websockets


# --- 配置 ---
BASE_URL = os.getenv("BENCH_BASE_URL", "http://127.0.0.1:8000")
WS_URL = BASE_URL.replace("http", "ws") + "/ws"


# --- 工具函数 ---
async def register_user(client: httpx.AsyncClient, suffix: int) -> dict:
    """注册一个测试用户，返回 {token, user_id}"""
    phone = f"+86138{10000000 + suffix:08d}"
    resp = await client.post("/api/auth/register", json={
        "phone": phone,
        "username": f"bench_{suffix}",
        "display_name": f"Bench{suffix}",
        "password": "bench123",
    })
    if resp.status_code == 400:
        # 用户已存在，走登录
        resp = await client.post("/api/auth/login", json={
            "phone": phone,
            "password": "bench123",
        })
    data = resp.json()
    return {
        "token": data["access_token"],
        "user_id": data["user"]["id"],
    }


@dataclass
class BenchResult:
    name: str
    total: int = 0
    success: int = 0
    failures: int = 0
    latencies: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.success / self.total if self.total else 0

    def p50(self) -> float:
        if not self.latencies:
            return 0
        sorted_lats = sorted(self.latencies)
        return sorted_lats[len(sorted_lats) // 2]

    def p99(self) -> float:
        if not self.latencies:
            return 0
        return sorted(self.latencies)[int(len(self.latencies) * 0.99)]

    def avg(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0

    def print(self):
        print(f"\n  [{self.name}]")
        print(f"    总数: {self.total}, 成功: {self.success}, 失败: {self.failures}")
        print(f"    成功率: {self.success_rate:.1%}")
        if self.latencies:
            print(f"    延迟(ms): avg={self.avg()*1000:.1f}, p50={self.p50()*1000:.1f}, p99={self.p99()*1000:.1f}")


# --- 场景 1: 并发连接测试 ---
async def scenario_connect(token: str, idx: int, result: BenchResult):
    """单个客户端：连接 → ping/pong 一次 → 断开"""
    t0 = time.perf_counter()
    try:
        async with websockets.connect(
            f"{WS_URL}?token={token}",
            max_size=2**24,
            close_timeout=2,
        ) as ws:
            await ws.send(json.dumps({"type": "ping"}))
            resp = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(resp)
            if data.get("type") == "pong":
                result.success += 1
            else:
                result.failures += 1
    except Exception as e:
        result.failures += 1
        if result.failures <= 3:
            print(f"    [client {idx}] 连接失败: {type(e).__name__}: {e}")
    finally:
        elapsed = time.perf_counter() - t0
        result.latencies.append(elapsed)


async def bench_concurrent_connections(num_clients: int) -> BenchResult:
    result = BenchResult(name=f"并发连接测试 ({num_clients} clients)")
    result.total = num_clients

    print(f"\n{'='*50}")
    print(f"场景1: {num_clients} 并发 WebSocket 连接")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        print("  注册/登录测试用户...")
        users = []
        for i in range(num_clients):
            user = await register_user(client, i)
            users.append(user)
            if (i + 1) % 50 == 0:
                print(f"    {i + 1}/{num_clients}")

    print(f"  建立 {num_clients} 个 WebSocket 连接...")
    t0 = time.perf_counter()
    tasks = [scenario_connect(u["token"], i, result) for i, u in enumerate(users)]
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    print(f"  耗时: {elapsed:.1f}s")
    print(f"  连接速率: {num_clients / elapsed:.0f} conn/s")
    result.print()
    return result


# --- 场景 2: 消息吞吐测试 ---
async def scenario_throughput(
    token: str,
    sender_id: str,
    receiver_id: str,
    num_messages: int,
    result: BenchResult,
    sem: asyncio.Semaphore,
):
    """单个客户端持续发消息"""
    first_error_shown = False
    try:
        async with websockets.connect(
            f"{WS_URL}?token={token}",
            max_size=2**24,
            close_timeout=5,
        ) as ws:
            for _ in range(num_messages):
                async with sem:  # 限制并发，避免 SQLite 写锁竞争
                    msg_id = str(uuid.uuid4())
                    t0 = time.perf_counter()
                    await ws.send(json.dumps({
                        "type": "message",
                        "msg_id": msg_id,
                        "payload": {
                            "receiver_id": receiver_id,
                            "content": f"bench msg {msg_id[:8]}",
                        },
                    }))
                    try:
                        resp = await asyncio.wait_for(ws.recv(), timeout=15)
                        elapsed = time.perf_counter() - t0
                        data = json.loads(resp)
                        if data.get("type") == "message_ack":
                            result.success += 1
                            result.latencies.append(elapsed)
                        else:
                            result.failures += 1
                            if not first_error_shown:
                                print(f"\n    非预期响应: {data}")
                                first_error_shown = True
                    except asyncio.TimeoutError:
                        result.failures += 1
    except Exception as e:
        result.failures += num_messages
        if result.failures <= num_messages + 1:
            print(f"    WS 错误: {type(e).__name__}: {e}")


async def bench_message_throughput(
    num_clients: int,
    msgs_per_client: int,
) -> BenchResult:
    total = num_clients * msgs_per_client
    result = BenchResult(name=f"消息吞吐测试 ({num_clients} 客户端 x {msgs_per_client} 消息)")
    result.total = total

    print(f"\n{'='*50}")
    print(f"场景2: 消息吞吐测试 — {num_clients} 客户端各发 {msgs_per_client} 条消息")
    print(f"  (SQLite 单写者限制，消息串行发送)")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        print("  准备测试用户（需要2倍数量：发送方+接收方）...")
        users = []
        for i in range(num_clients * 2):
            user = await register_user(client, i + 10000)
            users.append(user)
            if (i + 1) % 50 == 0:
                print(f"    {i + 1}/{num_clients * 2}")

    sem = asyncio.Semaphore(1)
    progress = {"done": 0}

    print(f"  发送 {total} 条消息...")
    t0 = time.perf_counter()
    tasks = []
    for i in range(num_clients):
        sender = users[i]
        receiver = users[num_clients + i]
        tasks.append(scenario_throughput(
            sender["token"],
            sender["user_id"],
            receiver["user_id"],
            msgs_per_client,
            result,
            sem,
        ))
    await asyncio.gather(*tasks)
    elapsed = time.perf_counter() - t0

    print(f"  耗时: {elapsed:.1f}s")
    print(f"  吞吐量: {total / elapsed:.0f} msg/s")
    result.print()
    return result


# --- 场景 3: 逐步加压（找连接上限） ---
async def bench_stress_test(
    start: int = 50,
    step: int = 50,
    max_clients: int = 1000,
):
    """逐步增加连接数，直到成功率低于 95%"""
    print(f"\n{'='*50}")
    print(f"场景3: 逐步加压 — 从 {start} 连接开始，每次 +{step}，上限 {max_clients}")

    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        for num in range(start, max_clients + 1, step):
            print(f"\n  --- {num} 连接 ---")
            users = []
            for i in range(num):
                user = await register_user(client, i + 20000)
                users.append(user)

            result = BenchResult(name=f"stress_{num}", total=num)
            t0 = time.perf_counter()
            tasks = [scenario_connect(u["token"], i, result) for i, u in enumerate(users)]
            await asyncio.gather(*tasks)
            elapsed = time.perf_counter() - t0

            print(f"    连接速率: {num / elapsed:.0f} conn/s, 成功率: {result.success_rate:.1%}")
            if result.success_rate < 0.95:
                print(f"\n  ⚠ 成功率跌破 95%，拐点约在 {num} 连接")
                break


# --- 主入口 ---
async def main():
    parser = argparse.ArgumentParser(description="WebSocket 压测")
    parser.add_argument("--clients", type=int, default=100, help="并发连接数（默认100）")
    parser.add_argument("--messages", type=int, default=10, help="每客户端消息数（默认10）")
    parser.add_argument("--stress", action="store_true", help="执行加压测试")
    parser.add_argument("--skip-connect", action="store_true", help="跳过连接测试")
    parser.add_argument("--skip-message", action="store_true", help="跳过消息测试")
    args = parser.parse_args()

    # 先检查服务是否可达
    print("检查服务连通性...")
    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=5) as client:
            resp = await client.get("/docs")
            if resp.status_code != 200:
                print(f"服务不可达，请先启动: uvicorn app.main:app --host 127.0.0.1 --port 8000")
                return
    except Exception as e:
        print(f"无法连接到 {BASE_URL}: {e}")
        print("请先启动: uvicorn app.main:app --host 127.0.0.1 --port 8000")
        return

    print("服务已连接，开始压测...")

    if not args.skip_connect:
        await bench_concurrent_connections(args.clients)

    if not args.skip_message:
        await bench_message_throughput(
            num_clients=min(args.clients, 50),  # 消息测试用较少客户端
            msgs_per_client=args.messages,
        )

    if args.stress:
        await bench_stress_test()


if __name__ == "__main__":
    asyncio.run(main())
