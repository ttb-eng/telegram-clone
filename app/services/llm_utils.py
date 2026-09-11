from langchain_community.chat_models.openai import ChatOpenAI
from langchain_core.callbacks import CallbackManager, CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from pydantic import Field
import re
from langchain_core.outputs import ChatGeneration
from typing import Any

class DeepSeekJsonWrapper(BaseChatModel):
    model_config = {"arbitrary_types_allowed": True}
    llm:Any=Field(default=None)


    @property
    def _llm_type(self)->str:
        return 'deepseek-chat'



    def _strip_json_fence(self,text:str)->str:
        if not text:
            return text
        text = re.sub(r'^```(?:json)?\s*\n?', '', text)
        text =  re.sub(r'\n?```\s*$', '', text)
        return text.strip()
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = self.llm._generate(messages, stop, run_manager, **kwargs)  # 委托
        for gen_list in result.generations:
            gen = gen_list[0] if isinstance(gen_list, list) else gen_list
            gen.text = self._strip_json_fence(gen.text)
            if gen.message and gen.message.content:
                gen.message.content = self._strip_json_fence(gen.message.content.strip())
        return result

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        result = await self.llm._agenerate(messages, stop, run_manager, **kwargs)  # 委托
        for gen_list in result.generations:
            gen = gen_list[0] if isinstance(gen_list, list) else gen_list
            gen.text = self._strip_json_fence(gen.text)
            if gen.message and gen.message.content:
                gen.message.content = self._strip_json_fence(gen.message.content.strip())
        return result






