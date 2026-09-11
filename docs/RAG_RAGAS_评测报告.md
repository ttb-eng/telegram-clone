# RAG 文档问答系统 — RAGAS 量化评测报告

**作者：** [你的姓名]  
**项目：** Telegram Clone — AI 智能助手  
**代码仓库：** https://github.com/ttb-eng/-telegram-clone  
**线上地址：** https://mytelegram.xyz/docs

---

## 一、项目概述

在 Telegram Clone 项目中实现了基于 RAG（检索增强生成）的文档问答功能。用户上传文档后，系统自动分块、向量化并存入 ChromaDB 向量数据库；提问时检索相关片段，交由 DeepSeek 大模型增强生成回答。为量化评估系统质量，基于 RAGAS 框架设计了 15 题跨文档评测方案。

---

## 二、技术架构

```
用户上传文档 → chunk_text (500字符滑动窗口)
              → SentenceTransformer (all-MiniLM-L6-v2, 384维)
              → ChromaDB (cosine空间, 用户级隔离)
              ↓
用户提问     → Embedding → Cosine检索 (top-5 + 距离过滤)
              → 拼接上下文 → DeepSeek Chat → 增强生成回答
```

| 组件 | 技术选型 |
|------|----------|
| 向量数据库 | ChromaDB (PersistentClient) |
| Embedding 模型 | sentence-transformers/all-MiniLM-L6-v2 (384维) |
| LLM | DeepSeek Chat API |
| 评测框架 | RAGAS |
| 用户隔离 | user_id 元数据过滤 + 闭包注入 |

---

## 三、评测方案

### 评测文档（3 篇，跨域设计）
- `python_decorator.txt` — Python 装饰器语法
- `redis_cache.txt` — Redis 缓存策略
- `search_engine.txt` — 搜索引擎原理

### 评测题目（15 题，三种题型）
| 题型 | 示例 | 数量 |
|------|------|------|
| 单文档提取 | "装饰器使用什么符号？" | 6 题 |
| 跨文档对比 | "倒排索引和装饰器都用到了什么共同概念？" | 4 题 |
| 多文档整合 | "三篇文档中分别提到了哪些排序相关内容？" | 5 题 |

### 评测流程
```
存储 3 篇文档 → 逐题检索 top-5 → 构建 system prompt → DeepSeek 生成回答
→ 收集 15 组 (question, answer, contexts, ground_truth) → RAGAS evaluate
```

---

## 四、评测结果

| 指标 | 分数 | 说明 |
|------|------|------|
| **Faithfulness**（忠实度） | 0.73 | 生成回答与检索内容的吻合程度 |
| **Answer Relevancy**（回答相关性） | 0.77 | 回答与问题的语义相关性 |
| **Context Recall**（上下文召回） | 0.79 | 检索到的内容覆盖标准答案的比例 |
| **Context Precision**（上下文精度） | 0.36 | 检索结果中相关内容的比例 |

> 评测环境：15 题 × 4 指标 = 60 个评估任务，评测 LLM 为 DeepSeek Chat，Embedding 为 all-MiniLM-L6-v2，完整可复现（`tests/test_rag_ragas.py`）。

---

## 五、分析与优化方向

**已优化：**
- 引入 distance 阈值过滤（cosine distance < 0.8），减少检索噪声
- 实现 LLM 输出 JSON 围栏自动剥离（DeepSeekJsonWrapper），确保 RAGAS 评估流程零报错

**待优化：**
- **Chunking 策略**：当前 chunk_size=500，过粗的切片引入无关内容，导致 context_precision 偏低。计划调整为 200~300 并增大 overlap，配合 semantic chunking
- **Re-rank**：检索 top-5 后引入 cross-encoder 重排序，提升检索精度
- **混合检索**：BM25 + 向量检索融合，提升中英文混合场景下的召全率

---

## 六、技术关键点

- **全异步架构**：FastAPI + SQLAlchemy Async + httpx，检索和 LLM 调用均为异步
- **用户级隔离**：ChromaDB metadata 按 user_id 过滤，`search_knowledge` 工具通过闭包注入 user_id，确保多用户知识库互不干扰
- **评测可复现**：pytest + asyncio，15 组 eval cases 写死在测试文件中，一键运行
- **DeepSeek 兼容**：自研 `DeepSeekJsonWrapper` 解决 DeepSeek 返回 JSON 带 markdown 围栏的问题，基于 LangChain `BaseChatModel` 规范封装

---

*评测代码：`tests/test_rag_ragas.py` | 生成日期：2026-08-02*
