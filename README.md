# RAG Knowledge Assistant

基于 **FastAPI + LangGraph + BGE-M3 + Milvus** 的知识库问答系统，支持 PDF 知识库构建、Dense/Sparse Hybrid Retrieval、历史对话、SSE 流式回答，并通过 Frozen Evaluation 与组件消融验证检索方案。

> 这是一个面向 AI 应用开发 / RAG / AI Testing / FDE 实习展示的工程项目，不宣称为 enterprise production-grade 系统。

## Demo / 项目展示

### 文档上传与知识库构建

上传 PDF 后，系统调用 MinerU 解析为 Markdown，完成标题感知切分、BGE-M3 向量化并写入 Milvus。

<img alt="PDF upload and knowledge-base ingestion" height="450" src="docs/images/upload.png" width="300"/>

### RAG 智能问答

聊天页面支持知识库问答、SSE 增量输出及结构化 Sources 展示。

<img alt="RAG chat interface" height="700" src="docs/images/chat.png" width="900"/>

<img alt="RAG answer and sources" height="800" src="docs/images/chatresult.png" width="950"/>

### 历史会话管理

MongoDB 按 `session_id` 保存对话，前端可查看并恢复最近会话。

<img alt="MongoDB-backed conversation history" height="400" src="docs/images/history.png" width="350"/>

### Demo Video

[View the complete running demo](https://github.com/bnd0530ming1204-dotcom/rag-knowledge-assistant/releases/tag/v1.0.0)

## Features

- **PDF / Markdown 知识库构建**：MinerU PDF 解析、Markdown 资源处理、heading-aware chunking 与同名文档更新。
- **BGE-M3 Hybrid Retrieval**：一次编码生成 Dense 与 Sparse vectors，通过 Milvus 进行 0.8/0.2 混合检索。
- **Conversation memory**：MongoDB 保存对话历史；有历史时进行 history-aware query rewrite，改写失败则使用原 Query。
- **FastAPI API**：提供文档上传、问答、历史会话与 SSE endpoints。
- **SSE streaming**：逐 token `delta`、完整 `final`、结构化 `error` 及明确终止。
- **Structured sources**：回答返回 document/file identity、chunk identity 与 title；不伪造 page number。
- **Reliability handling**：区分正常空检索与 embedding、Milvus、retrieval infrastructure failure。
- **Evaluation-driven decisions**：使用 Frozen Dataset、Recall/MRR、Latency 和 ablation 决定默认检索链路，而非只展示功能效果。

## Architecture

### Document Ingestion

```text
PDF / Markdown
→ MinerU / Markdown processing
→ heading-aware chunking
→ parent-heading context enrichment
→ BGE-M3 dense + sparse embeddings
→ Milvus
```

### Query Pipeline

```text
Query
→ optional history-aware rewrite
→ BGE-M3 Dense/Sparse Hybrid Retrieval 0.8/0.2
→ Candidate10 → Final Top5 Context
→ LLM Answer
→ Sources / SSE / MongoDB History
```

Parent-heading enrichment 为保持 ingestion representation 兼容而保留，但 Frozen V2 没有测得检索收益。Earlier versions evaluated HyDE, custom RRF and reranking; after ablation, they are preserved as experimental/history modules but disabled in the default production graph. Cliff cutoff 已从默认链路移除。

## Why This Is More Than a Basic RAG Demo

1. **Frozen Evaluation**：使用冻结且带 SHA-256 manifest 的 110-query synthetic benchmark，避免优化过程中静默改题。
2. **Component Ablation**：独立比较 Dense、Sparse、Hybrid、Parent Heading、HyDE、Rerank、cutoff 与 candidate budget。
3. **Evidence-based trade-offs**：同时报告 Recall@K、MRR@5 与真实 wall-clock latency，并保留 Recall@3 下降等负面结果。
4. **Reliability semantics**：正常 `NO_RESULT` 不等于 `RETRIEVAL_ERROR`；FastAPI/SSE 对基础设施故障返回脱敏结构化错误。

## Evaluation

Evaluation V2 使用 **SYNTHETIC / FOR EVALUATION ONLY** 的智能办公设备语料，不是真实企业内部数据。Dataset 包含 10 documents、110 Frozen queries（90 answerable / 20 no-answer）和 39 个 production-ingestion chunks。

| Metric | Original full pipeline | Final default pipeline |
| --- | ---: | ---: |
| Recall@1 | 0.6444 | 0.6481 |
| Recall@3 | **0.8741** | **0.8574 ↓** |
| Recall@5 | 0.8907 | 0.8944 |
| MRR@5 | 0.8120 | 0.8204 |
| Retrieval P50 | 2623.1 ms | 85.8 ms* |

`*` 本地 Frozen evaluation 的 wall-clock observation，不是 production SLA。最终配置主要收益是显著简化链路和降低本地检索延迟，同时 Recall@5/MRR 基本保持并略升；**Recall@3 确实下降，不能描述为所有指标全面提升。**

完整实验与逐项决策：

- [Phase 2 Ablation Report](evaluation_v2/reports/phase2_ablation_report.md)
- [Phase 3 Targeted Optimization Report](evaluation_v2/reports/phase3_targeted_optimization_report.md)
- [RAG Engineering Decisions](docs/RAG_ENGINEERING_DECISIONS.md)
- [Evaluation V2 README](evaluation_v2/README.md)

## Key Engineering Decisions

- **Hybrid — 保留**：0.8/0.2 在 early ranking 上更合适，但并非所有指标都优于单路检索。
- **Candidate10 — 保留**：扩大初始候选池，最终仍只向回答阶段传入 Top5。
- **HyDE — 默认关闭**：只改善少量尾部 Query，却显著增加延迟，并在 no-answer Query 上产生无依据断言。
- **Current reranker — 默认关闭**：增加外部服务延迟，并使 Recall@1 / MRR 回退。
- **Cliff cutoff — 移除**：曾删除 relevant evidence，且没有验证收益。
- **Evidence Gate v1 — 未上线**：Frozen test 的误拒率不可接受，因此不能声称系统已可靠解决 no-answer/hallucination。

## Quick Start

### 1. 环境

- Python 3.11
- Docker Desktop / Docker Compose
- MinerU API 与 OpenAI-compatible LLM API
- 本地 BGE-M3 模型或可用的模型下载环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

根据 [.env.example](.env.example) 配置 API、BGE-M3、Milvus、MongoDB 与 MinIO；不要提交真实密钥。

### 2. 启动依赖

Compose 包含 Milvus、etcd、MinIO 和 MongoDB：

```powershell
docker compose up -d
docker compose ps
```

### 3. 启动 FastAPI

```powershell
.\.venv\Scripts\uvicorn.exe web.api.query_service:app --host 127.0.0.1 --port 8001
```

打开聊天页面：`http://127.0.0.1:8001/chat.html`

Swagger UI：`http://127.0.0.1:8001/docs`

### 4. Upload PDF / Chat

1. 在聊天页面或 `POST /upload` 上传 PDF，等待返回 `chunks_count`。
2. 调用 `POST /chat`：

```json
{
  "query": "这份文档的主要内容是什么？",
  "session_id": "demo-session-001",
  "is_stream": true
}
```

3. 流式请求随后连接 `GET /stream/demo-session-001`；使用相同 `session_id` 可测试历史改写，并可通过 `GET /history/demo-session-001` 查看记录。

### 5. Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_final*.py" -v
```

最终验收包含 12 个 unit/API/SSE behavior tests，以及真实 BGE-M3→Milvus 和 MongoDB 的 2 个 integration tests。

## Main API Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/upload` | 上传 PDF 并同步解析、切分、向量化和入库 |
| `POST` | `/chat` | 普通或流式知识库问答 |
| `GET` | `/stream/{session_id}` | 接收 SSE delta/final/error events |
| `GET` | `/history/{session_id}` | 获取单个会话消息 |
| `GET` | `/history` | 获取最近会话列表 |
| `GET` | `/chat.html` | 打开内置聊天页面 |


