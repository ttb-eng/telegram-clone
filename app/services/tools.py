import logging
from datetime import datetime

import httpx
import pytz

logger=logging.getLogger(__name__)
CITY_TIMEZONE = {
    "北京": "Asia/Shanghai",
    "上海": "Asia/Shanghai",
    "东京": "Asia/Tokyo",
    "纽约": "America/New_York",
    "伦敦": "Europe/London",
    "巴黎": "Europe/Paris",
    "悉尼": "Australia/Sydney",
    "莫斯科": "Europe/Moscow",
    "洛杉矶": "America/Los_Angeles",
    "首尔": "Asia/Seoul",
    "新加坡": "Asia/Singapore",
    "香港": "Asia/Hong_Kong",
    "迪拜": "Asia/Dubai",
}

TOOLS=[
    {
        "type":"function",
        "function":{
            "name":"get_time",
            "description":"查询指定城市当前的时间点",
            "parameters":{
                "type":"object",
                "properties":{
                    "city":{
                        "type":"string",
                        "description":"城市名称，如北京"
                    }
                },
                "required":["city"],
            },
        },
    },
    {
        "type":"function",
        "function":{
            "name":"get_weather",
            "description":"查询天气",
            "parameters":{
                "type":"object",
                "properties":{
                    "city":{
                        "type":"string",
                        "description":"目前没有定位功能，需要你手动输入你所在城市，来查询天气"
                    }
                },
                "required":["city"],

            },
        },
    },
    {
        "type":"function",
        "function":{
            "name":"web_search",
            "description":"联网搜索",
            "parameters":{
                "type":"object",
                "properties":{
                    "query":{
                        "type":"string",
                        "description":"搜索关键词",
                    }
                },
                "required":["query"],
            },

        },
    },
    {
        "type":"function",
        "function":{
            "name":"search_knowledge",
            "description":"查询用户上传的文档知识库，获取相关文档内容。当用户询问关于自己上传的文件、文档内容时使用此工具。",
            "parameters":{
                "type":"object",
                "properties":{
                    "query":{
                        "type":"string",
                        "description":"在文档知识库中搜索的关键词或问题",
                    }
                },
                "required":["query"],
            },

        },
    },
]



async def execute_tools(name: str, args: dict, user_id=None) -> str:
    func = TOOLS_FUNCTIONS.get(name)
    if not func:
        return f"还没有{name}功能"
    if user_id is not None and "user_id" in func.__code__.co_varnames:
        return await func(user_id=user_id, **args)
    return await func(**args)

async def _get_time(city:str)->str:
    tz_name=CITY_TIMEZONE.get(city)
    if not tz_name:
        return f"抱歉，无法查询到{city}的时间"
    try:
        tz=pytz.timezone(tz_name)
        now=datetime.now(tz)
        return f"{city}现在的时间是：{now.strftime('%Y-%m-%d %H:%M:%S')}"
    except Exception as e:
        return f"查询失败的原因是:{e}"

async def _get_weather(city:str)->str:
    url = f"https://wttr.in/{city}?format=%C+%t+%h+%w"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        return f"{city} 天气: {resp.text.strip()}"




async def _web_search(query: str) -> str:
    api_key = __import__("app.config", fromlist=["settings"]).settings.tavily_api_key
    if not api_key:
        return "搜索功能未配置（缺少 Tavily API Key）"

    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": 5,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return f"未找到关于「{query}」的信息"
            lines = []
            for r in results:
                title = r.get("title", "")
                snippet = r.get("content", "")
                lines.append(f"{title}: {snippet}")
            return "\n".join(lines)
    except Exception as e:
        return f"搜索失败: {e}"

async def _search_knowledge(query: str, user_id=None) -> str:
    if user_id is None:
        return "无法确定用户身份，请先登录"
    from app.services.rag import search_similar
    from uuid import UUID

    uid = UUID(user_id) if isinstance(user_id, str) else user_id
    chunks = await search_similar(query, uid, top_k=5)
    if not chunks:
        return "你的文档知识库中暂无相关内容"

    lines = []
    for i, c in enumerate(chunks):
        filename = c["metadata"].get("filename", "未知文档")
        lines.append(f"[{i+1}] 来自《{filename}》: {c['content']}")
    return "\n\n".join(lines)


TOOLS_FUNCTIONS = {
    "get_time": _get_time,
    "get_weather": _get_weather,
    "web_search": _web_search,
    "search_knowledge": _search_knowledge,
}