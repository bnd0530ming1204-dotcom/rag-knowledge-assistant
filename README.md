# RAG Knowledge Assistant

## 项目简介

基于 **Python、FastAPI 与 LangGraph** 构建的端到端 RAG 知识库问答系统，支持 PDF/Markdown 文档解析与知识入库、多轮对话、Query Rewrite、BGE-M3 Dense + Sparse Hybrid Retrieval、上下文构建、LLM 流式生成与来源追踪。系统结合 Milvus 管理向量检索、MongoDB 保存会话历史，并通过结构化异常处理、Fallback 与 Request Trace 提升应用链路的可观测性和稳定性。

## Demo / 项目效果

### 文档上传与知识库构建

<img alt="PDF upload and knowledge-base ingestion" height="450" src="docs/images/upload.png" width="300"/>

### Knowledge QA

<img alt="RAG chat interface" height="700" src="docs/images/chat.png" width="900"/>

### Answer + Sources

<img alt="RAG answer and sources" height="800" src="docs/images/chatresult.png" width="950"/>

### Conversation History

<img alt="MongoDB-backed conversation history" height="400" src="docs/images/history.png" width="350"/>

### Demo Video

[查看 GitHub Release 中的完整运行演示](https://github.com/bnd0530ming1204-dotcom/rag-knowledge-assistant/releases/tag/v1.0.0)

## 核心功能

- PDF / Markdown 文档导入与 MinerU 解析
- Heading-aware / hierarchical chunking 与 parent metadata
- BGE-M3 Dense + Sparse embedding
- Milvus Weighted Hybrid Retrieval
- Conditional / history-aware Query Rewrite 与原 Query fallback
- 可配置 Explicit RRF、Rerank、HyDE Router、Fixed / Dynamic Context Selector
- Context 去重、同 parent 控制与 token budget
- qwen-flash Answer Generation 与结构化 Sources
- SSE `delta → final/error → close` 增量输出
- MongoDB Conversation History
- Structured errors、reliability fallback 与 request trace

## 系统架构

系统由文档知识构建、在线问答和基础设施三部分组成：文档经解析、切分和向量化进入 Milvus；查询结合历史完成检索与上下文构建，再由 LLM 流式生成回答并返回来源；MongoDB、SSE 与 Request Trace 支撑会话和运行状态管理。

## 文档处理流程

```text
PDF / Markdown
→ MinerU / Markdown Processing
→ Cleaner
→ Heading-aware / Hierarchical Chunking
→ Metadata / Parent Heading
→ BGE-M3 Dense + Sparse Embeddings
→ Milvus
```

## 问答流程

```text
User Query
→ MongoDB History
→ History-aware Rewrite
→ BGE-M3 Dense + Sparse Retrieval
→ Weighted Hybrid 0.8 / 0.2
→ Candidate10
→ Fixed Top5 Context Builder
→ qwen-flash
→ Answer + Structured Sources
→ SSE Streaming
→ MongoDB History
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Application | Python 3.11, FastAPI, LangGraph |
| Document Processing | MinerU, Markdown |
| Embedding | BGE-M3 Dense + Sparse |
| Retrieval | Milvus, Weighted Hybrid, optional RRF / Rerank / HyDE |
| Generation | DashScope, qwen-flash |
| History | MongoDB |
| Streaming | Server-Sent Events |
| Infrastructure | Docker Compose, Milvus, MinIO, etcd, MongoDB |

## 工程设计与可靠性

- Embedding / Milvus / Generation 异常返回 typed structured error
- Query Rewrite failure 自动使用 original query
- HyDE / Rerank failure 自动回退基础检索结果
- Mongo read failure 进入 stateless mode，write failure 不影响已生成答案
- SSE 支持 `COMPLETED / FAILED / TIMEOUT / CANCELLED` 终态
- Request Trace 记录 strategy、candidates、context tokens、latency、fallback 与 error
- Context token budget、metadata normalization 与 source deduplication
- Docker Compose 管理 Milvus、MinIO、etcd 与 MongoDB

## 检索优化与技术选型

针对知识库检索中的语义匹配、关键词匹配和复杂查询场景，项目对 Dense、Sparse、Weighted Hybrid、Explicit RRF、Rerank、HyDE 与 Context Selection 等方案进行了可复现实验，并结合检索质量、延迟和链路稳定性选择最终默认方案。

- 110-query evaluation set（90 Answerable / 20 No-answer）
- 10 Synthetic Evaluation Documents，Dataset / Corpus Hash Freeze
- 真实 BGE-M3、Milvus、`gte-rerank-v2` 与 `qwen-flash` 实验

最终默认检索与生成链路：

```text
History-aware Rewrite
→ BGE-M3 Weighted Hybrid 0.8 / 0.2
→ Candidate10
→ Fixed Top5
→ qwen-flash
```

## 核心结果

| Final Retrieval Metric | Result |
| --- | ---: |
| Recall@1 | 0.6481 |
| Recall@3 | 0.8574 |
| Recall@5 | 0.8944 |
| MRR@5 | 0.8204 |
| Retrieval / Context P50 | 75.89 ms |
| Retrieval / Context P95 | 120.85 ms |

| Verification | Result |
| --- | ---: |
| Automated tests | 66 passed, 0 failed |
| Real Milvus integration | PASS |
| Real MongoDB integration | PASS |

## Quick Start

需要 Python 3.11、Docker Desktop / Docker Compose、可用的 MinerU 与 OpenAI-compatible LLM API，以及本地 BGE-M3 模型或可用的下载环境。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d
docker compose ps
.\.venv\Scripts\uvicorn.exe web.api.query_service:app --host 127.0.0.1 --port 8001
```

- Chat UI：`http://127.0.0.1:8001/chat.html`
- Swagger：`http://127.0.0.1:8001/docs`

运行验收测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_final*.py" -v
```

## 项目结构

```text
config/                 应用与检索配置
processor/              文档导入与 Query Graph 节点
utils/                  Embedding、Milvus、Mongo、Context 与可靠性工具
web/                    FastAPI API 与内置 Chat UI
evaluation_v2/          Frozen dataset 与历史实验 artifacts
evaluation_v3/          最终策略、Generation 与 regression artifacts
test/                   Unit、acceptance 与 integration tests
docs/                   工程决策、简历证据与 Demo assets
```

## Technical Reports / 技术文档

- [RAG V3 Final Report](evaluation_v3/reports/RAG_V3_FINAL_REPORT.md)
- [RAG Engineering Decisions](docs/RAG_ENGINEERING_DECISIONS.md)
- [Resume-safe Evidence](docs/RESUME_EVIDENCE.md)
- [Evaluation V2 and Artifacts](evaluation_v2/README.md)
