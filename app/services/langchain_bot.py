import logging
from collections.abc import AsyncGenerator

import certifi
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.services.tools import (
    _get_time,
    _get_weather,
    _web_search,
    _search_knowledge,
)

logger = logging.getLogger(__name__)

_async_client = None
_sync_client = None


def _get_async_client() -> httpx.AsyncClient:
    global _async_client
    if _async_client is None:
        _async_client = httpx.AsyncClient(verify=certifi.where(), timeout=30)
    return _async_client


def _get_sync_client() -> httpx.Client:
    global _sync_client
    if _sync_client is None:
        _sync_client = httpx.Client(verify=certifi.where(), timeout=30)
    return _sync_client


def _make_tools(user_id: str | None):
    """为每个请求创建 LangChain 工具，user_id 通过闭包注入到 search_knowledge。"""

    @tool
    async def get_time(city: str) -> str:
        """查询指定城市当前的时间点，如北京、东京、纽约等"""
        return await _get_time(city=city)

    @tool
    async def get_weather(city: str) -> str:
        """查询指定城市的天气信息"""
        return await _get_weather(city=city)

    @tool
    async def web_search(query: str) -> str:
        """联网搜索，获取最新信息"""
        return await _web_search(query=query)

    @tool
    async def search_knowledge(query: str) -> str:
        """查询用户上传的文档知识库，获取相关文档内容。当用户询问关于自己上传的文件时使用。"""
        if user_id is None:
            return "无法确定用户身份"
        return await _search_knowledge(query=query, user_id=user_id)

    return [get_time, get_weather, web_search, search_knowledge]


def _to_langchain_messages(messages: list[dict]) -> tuple[str, list]:
    """将 dict 格式消息转为 LangChain 消息。

    返回 (system_prompt, conversation_messages)
    """
    system_prompt = ""
    converted = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            system_prompt = content
        elif role == "user":
            converted.append(HumanMessage(content=content))
        elif role == "assistant":
            converted.append(AIMessage(content=content))
    return system_prompt, converted


async def get_ai_reply_langchain(messages: list, user_id=None) -> AsyncGenerator[str, None]:
    """LangChain 版 AI 回复 —— 使用 langgraph ReAct Agent 自动处理工具调用。

    与 deepseek.py 的手动 Tool Calling 循环形成对比：
    - 手写版：手动 while 循环判断 tool_calls，手动拼接 tool result
    - LangChain 版：@tool 装饰器 + create_react_agent，框架自动管理调用链
    """
    if not settings.deepseek_api_key:
        yield "AI服务器未配置"
        return

    try:
        llm = ChatOpenAI(
            model="deepseek-v4-pro",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_api_url,
            temperature=0,
            max_tokens=2000,
            timeout=30,
            http_client=_get_sync_client(),
            http_async_client=_get_async_client(),
        )

        tools = _make_tools(user_id)
        system_prompt, lc_messages = _to_langchain_messages(messages)

        agent = create_react_agent(
            llm,
            tools,
            prompt=system_prompt or "你是一个乐于助人的AI助手，回答简洁准确。请使用中文回复。",
        )

        async for event in agent.astream_events(
            {"messages": lc_messages},
            version="v2",
        ):
            if event.get("event") == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content

    except Exception as e:
        logger.warning(f"LangChain agent error: {e}")
        yield "AI回复出错"
