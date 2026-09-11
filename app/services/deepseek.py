import logging

from openai import AsyncOpenAI
import json
from app.config import settings
from app.services.tools import TOOLS,execute_tools

from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


async def get_ai_reply_with_tools(messages: list, user_id=None) -> AsyncGenerator[str, None]:
    max_steps = 0
    if not settings.deepseek_api_key:
        yield "AI服务器未配置"
        return

    try:
        client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_api_url,
        )
        response = await client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=2000,
            timeout=30,
            stream=False,
        )
        reply=response.choices[0].message
        while reply.tool_calls:
            max_steps+=1
            if max_steps >= 10:
                yield "这个问题过于复杂，我先按照已有信息回复"
                break
            messages.append(reply.model_dump())
            for ct in reply.tool_calls:
                func_name=ct.function.name
                func_args=json.loads(ct.function.arguments)
                logger.info(f"AI调用了：{func_name}({func_args})")

                result=await execute_tools(func_name, func_args, user_id)

                messages.append({
                    "role":"tool",
                    "tool_call_id":ct.id,
                    "content":result,

                    })
            response = await client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                max_tokens=2000,
                timeout=30,
                stream=False,
            )
            reply=response.choices[0].message

        stream = await client.chat.completions.create(
            model="deepseek-v4-pro",
            messages=messages,
            max_tokens=2000,
            timeout=30,
            stream=True,
        )
        async for chunk in stream:
            delta=chunk.choices[0].delta.content
            if delta:
                yield delta
    except Exception as e:
        logger.warning(f"DeepSeek API error: {e}")
        yield "AI回复出错"
