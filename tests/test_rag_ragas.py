import os

import certifi
import pytest
import uuid

os.environ["SSL_CERT_FILE"] = certifi.where()

from langchain_openai import ChatOpenAI
from ragas import evaluate, EvaluationDataset
from wrapper import ceshi_Wrapper
from ragas.metrics import (
    Faithfulness,
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
)

from app.config import settings
from app.services import rag
from app.services.deepseek import get_ai_reply_with_tools


eval_cases = [
    {
        "question": "装饰器使用什么符号？",
        "ground_truth": "@ 符号",
    },
    {
        "question": "装饰器最常见的用途有哪些？",
        "ground_truth": "日志记录、性能计时、权限校验、缓存",
    },
    {
        "question": "自定义装饰器时需要注意什么？",
        "ground_truth": "使用 *args/**kwargs 适配任意参数、使用 @functools.wraps保留原函数元信息、带参数的装饰器需要三层嵌套",
    },
    {
        "question": "多个装饰器的执行顺序是怎样的？",
        "ground_truth": "从下往上执行，离函数最近的先执行",
    },
    {
        "question": "Cache-Aside 策略的工作流程是什么？",
        "ground_truth": "应用先查缓存，未命中则查数据库并回填缓存",
    },
    {
        "question": "缓存穿透和缓存击穿有什么区别？",
        "ground_truth": "缓存穿透是查询不存在的数据绕过缓存打DB，用布隆过滤器或缓存空值解决；缓存击穿是热点数据过期瞬间大量请求打DB，用互斥锁或永不过期解决",
    },
    {
        "question": "Redis 的两种持久化方式各有什么优缺点？",
        "ground_truth": "RDB 是定期全量备份，恢复快但可能丢数据；AOF 记录每条写命令，数据更安全但文件大恢复慢",
    },
    {
        "question": "缓存雪崩如何解决？",
        "ground_truth": "过期时间加随机值、主从+哨兵高可用",
    },
    {
        "question": "现代搜索引擎包含哪三个核心组件？",
        "ground_truth": "爬虫系统、索引系统、查询系统",
    },
    {
        "question": "什么是倒排索引？",
        "ground_truth": "一种从词到文档的映射结构，记录包含该词的文档列表及位置信息",
    },
    {
        "question": "建立索引前需要进行哪些文本预处理？",
        "ground_truth": "分词、去除停用词、词干提取",
    },
    {
        "question": "搜索引擎有哪些相关性排序算法？",
        "ground_truth": "TF-IDF 基于词频统计、PageRank考虑链接关系、现代使用机器学习模型综合多特征排序",
    },
    {
        "question": "文档中提到了哪些和缓存相关的技术？",
        "ground_truth": "Redis Cache-Aside、Read-Through、Write-Through、Write-Behind、functools 缓存",
    },
    {
        "question": "倒排索引和 Python装饰器都用到了什么共同概念？",
        "ground_truth": "两者没有直接关联，倒排索引是搜索用的数据结构，装饰器是 Python语法特性",
    },
    {
        "question": "三篇文档中分别提到了哪些排序相关内容?",
        "ground_truth": "搜索引擎的 TF-IDF/PageRank 排序、Redis没有直接提排序但有有序集合数据结构、装饰器文档没提排序",
    },
]


DOC1 = """Python 装饰器是一个可调用对象，它接受一个函数作为参数并返回一个替换函数。
  装饰器的核心语法是使用 @ 符号放在函数定义之前，等价于 func = decorator(func)。

  装饰器本质上是一个高阶函数，它利用了 Python 函数是一等公民的特性。
  最常见的装饰器用途包括：日志记录、性能计时、权限校验、缓存等。

  Python 内置了几个常用装饰器：
  - @staticmethod：定义静态方法，不需要 self 参数
  - @classmethod：定义类方法，第一个参数是 cls
  - @property：把方法变成属性访问
  - @functools.wraps：在自定义装饰器中保留原函数的元信息

  编写自定义装饰器时需要注意：
  1. 使用 *args 和 **kwargs 来适配任意参数的函数
  2. 使用 @functools.wraps 保留原函数的 __name__ 和 __doc__
  3. 带参数的装饰器需要三层嵌套函数

  装饰器的执行顺序是从下往上的，即离函数最近的装饰器先执行。
  例如 @decorator1 和 @decorator2 同时使用时，等效于 func = decorator1(decorator2(func))。"""

DOC2 = """Redis 是一个开源的内存数据结构存储系统，常用作数据库、缓存和消息代理。
  它支持多种数据结构，包括字符串、哈希、列表、集合和有序集合。

  Redis 作为缓存层时的常见策略：
  1. Cache-Aside（旁路缓存）：应用程序先查缓存，未命中则查数据库并回填缓存
  2. Read-Through：缓存层自动处理数据库读取，应用只与缓存交互
  3. Write-Through：写入时同时更新缓存和数据库
  4. Write-Behind：写入时只更新缓存，异步批量写入数据库

  缓存三大经典问题：
  - 缓存穿透：查询不存在的数据，绕过缓存直接打到数据库。解决方案：布隆过滤器或缓存空值
  - 缓存击穿：热点数据过期瞬间大量请求打到数据库。解决方案：互斥锁或永不过期
  - 缓存雪崩：大量缓存同时过期或 Redis 宕机。解决方案：过期时间加随机值、主从+哨兵高可用

  Redis 持久化有两种方式：RDB 快照和 AOF 日志。
  RDB 是定期全量备份，恢复快但可能丢失最近数据。
  AOF 记录每条写命令，数据更安全但文件更大恢复更慢。"""

DOC3 = """现代搜索引擎主要包含三个核心组件：爬虫系统、索引系统和查询系统。

  爬虫系统负责从互联网上抓取网页内容。爬虫从一组种子 URL 开始，
  沿着网页中的链接不断发现新页面。爬虫需要遵守 robots.txt 协议，
  并合理控制抓取频率以避免对目标服务器造成压力。

  索引系统将抓取到的网页内容构建为倒排索引。
  倒排索引是一种从词到文档的映射结构，类似于书的索引页。
  对于每个词，倒排索引记录了包含该词的文档列表以及词在文档中的位置信息。
  建立索引前通常需要进行文本预处理，包括分词、去除停用词、词干提取等步骤。

  查询系统处理用户的搜索请求。当用户输入查询词后，系统会：
  1. 对查询词进行同样的预处理
  2. 在倒排索引中查找匹配的文档
  3. 根据相关性排序算法对结果排序
  4. 返回排序后的结果列表

  相关性排序是搜索引擎的核心技术。早期的算法如 TF-IDF 基于词频统计，
  后来的 PageRank 算法考虑了网页之间的链接关系，
  现代搜索引擎则使用机器学习模型综合数百个特征进行排序。"""


@pytest.mark.asyncio
async def test_ragas_evaluation(test_user, db_session):
    # 1. 把 3 篇文档存入 ChromaDB
    await rag.store_document(
        user_id=test_user.id,
        filename="python_decorator.txt",
        text=DOC1,
        doc_id=uuid.uuid4(),
    )
    await rag.store_document(
        user_id=test_user.id,
        filename="redis_cache.txt",
        text=DOC2,
        doc_id=uuid.uuid4(),
    )
    await rag.store_document(
        user_id=test_user.id,
        filename="search_engine.txt",
        text=DOC3,
        doc_id=uuid.uuid4(),
    )

    # 2. 逐条检索 + AI 回答，收集 results
    results = []
    for case in eval_cases:
        chunks = await rag.search_similar(case["question"], test_user.id, top_k=5)

        context_parts = []
        for i, c in enumerate(chunks):
            context_parts.append(
                f"[来源{i + 1}: {c['metadata'].get('filename', '未知')}]\n{c['content']}"
            )
        context = "\n\n".join(context_parts)

        messages = [
            {
                "role": "system",
                "content": f"你是一个文档问答助手。请基于以下文档内容回答用户的问题。\n\n文档内容:\n{context}",
            },
            {"role": "user", "content": case["question"]},
        ]

        answer = ""
        async for chunk in get_ai_reply_with_tools(messages):
            answer += chunk

        results.append({
            "user_input": case["question"],
            "response": answer,
            "retrieved_contexts": [c["content"] for c in chunks],
            "reference": case["ground_truth"],
        })

    # 3. RAGAS 评估
    from app.services.llm_utils import DeepSeekJsonWrapper
    raw_llm = ChatOpenAI(
        model="deepseek-v4-pro",
        base_url=settings.deepseek_api_url,
        api_key=settings.deepseek_api_key,
    )
    eval_llm = DeepSeekJsonWrapper(llm=raw_llm)

    eval_embeddings = ceshi_Wrapper("all-MiniLM-L6-v2")

    ds = EvaluationDataset.from_list(results)
    scores = evaluate(
        ds,
        metrics=[
            Faithfulness(llm=eval_llm),
            AnswerRelevancy(llm=eval_llm, embeddings=eval_embeddings),
            ContextPrecision(llm=eval_llm),
            ContextRecall(llm=eval_llm),
        ],
        llm=eval_llm,
        embeddings=eval_embeddings,
    )
    print(scores)
