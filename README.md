# RAG Knowledge Assistant｜智能知识库问答系统

一个面向技术文档问答场景的 RAG（Retrieval-Augmented Generation）项目。系统将 PDF 解析、切分并写入向量数据库，在查询阶段通过 BGE-M3 混合检索、HyDE 双路召回、RRF 融合与模型重排，为 LLM 生成答案提供检索上下文。项目提供多轮会话、SSE 流式输出和简单的 Web 交互页面。

## 功能特性

- **文档导入**：支持通过 API 上传 PDF，调用 MinerU 获取 Markdown 解析结果，并完成切片、向量化和入库。
- **Dense + Sparse 混合检索**：使用 BGE-M3 同时生成稠密向量与稀疏向量，通过 Milvus Hybrid Search 兼顾语义相关性和关键词匹配。
- **双路召回与排序优化**：并行执行原问题检索和 HyDE 假设文档检索，使用 RRF 去重融合，再调用 DashScope TextReRank 精排并按分数断崖动态截断。
- **多轮对话增强**：通过 `session_id` 从 MongoDB 读取最近对话，利用 LLM 将追问改写为可独立检索的问题，并持久化用户与助手消息。
- **LangGraph 工作流编排**：将导入与查询拆分为状态驱动的节点工作流。
- **同步与流式问答**：FastAPI 提供同步问答和 SSE 增量输出，内置页面支持 PDF 上传、问答及历史记录查看。
- **图片资源处理**：当 MinerU 解析结果包含 `images` 目录时，扫描 Markdown 已引用的图片，为图片生成简短标题，上传至 MinIO 并替换 Markdown 中的本地链接；目录或有效引用不存在时跳过该节点的后续处理。
- **幂等文档更新**：以文件标题定位 Milvus 中的既有切片，重新导入同名文档时先删除旧数据再写入新数据。

## 系统流程

### 文档导入

```text
PDF 上传
  → MinerU API 解析为 Markdown
  → 可选：处理 Markdown 引用的图片并上传 MinIO
  → 按 Markdown 标题切分
  → 长块递归切分、短块合并
  → BGE-M3 生成 Dense / Sparse 向量
  → 创建或复用 Milvus Collection
  → 删除同名旧文档并批量入库
```

### RAG 问答

```text
用户问题 + session_id
  → 读取 MongoDB 最近 10 条会话
  → 多轮问题改写
  ├─ 原问题 Dense / Sparse 混合检索 ─┐
  └─ HyDE 生成假设文档并混合检索 ───┤
                                      → RRF 融合（Top 5）
                                      → DashScope TextReRank
                                      → 分数断崖动态截断（3～10 条）
                                      → 拼装知识片段与会话历史
                                      → LLM 生成答案
                                      → MongoDB 持久化 / SSE 流式推送
```

## 技术栈

| 模块 | 技术 |
| --- | --- |
| API 与交互 | FastAPI、Uvicorn、Pydantic、SSE、HTML/JavaScript |
| 工作流编排 | LangGraph |
| 文档解析 | MinerU API、Markdown、LangChain Text Splitters |
| Embedding | BGE-M3、FlagEmbedding（Dense + Sparse） |
| 检索与排序 | Milvus Hybrid Search、Weighted Ranker、HyDE、RRF、DashScope TextReRank |
| 模型调用 | LangChain、OpenAI 兼容接口、DashScope SDK |
| 数据存储 | Milvus、MongoDB、MinIO |
| 基础设施 | Docker Compose、etcd |

## 核心实现

### 1. 结构化文档切片

导入流程优先按 Markdown 一至六级标题组织章节；没有标题时使用文件名作为兜底标题。随后通过 `RecursiveCharacterTextSplitter` 处理超长章节，并合并过短内容，减少无语义碎片。默认参数如下：

- 最大切片长度：`2000` 字符
- 短块合并阈值：`500` 字符
- 句子级切分重叠：`1` 句

### 2. 图片资源处理

MinerU 解析结果包含 `images` 目录时，导入节点仅处理同时满足以下条件的资源：图片扩展名在支持列表中，并且图片文件已被 Markdown 正文引用。节点结合图片前后文调用 `VL_MODEL` 生成简短标题，将图片上传至 MinIO，再把 Markdown 中原有的本地图片引用替换为 MinIO URL。处理后的 Markdown 另存为 `_new.md` 文件；若图片目录或有效引用不存在，则直接沿用原 Markdown。

### 3. 混合检索与多路融合

每个知识切片同时保存 BGE-M3 的 Dense 和 Sparse 表示。查询时，Milvus 分别对 `dense_vector` 和 `sparse_vector` 执行 ANN 检索，并使用加权排序器合并结果。主查询图同时启动两条召回路径：

- **Query Retrieval**：直接对改写后的问题进行混合检索；
- **HyDE Retrieval**：先由 LLM 生成假设性答案文档，再将“问题 + 假设文档”向量化检索。

两路结果通过 RRF 按 `chunk_id` 融合，降低单一召回策略带来的偏差。

### 4. 精排与上下文控制

RRF 候选交给 DashScope TextReRank 重新打分。系统在排序结果的第 3～10 条之间查找最大相邻分差，以“分数断崖”确定最终上下文数量；答案节点还设置字符预算，控制知识片段与历史消息的 Prompt 长度。

### 5. 会话与流式响应

`POST /chat` 支持两种响应方式：

- `is_stream=false`：同步执行工作流并直接返回完整答案；
- `is_stream=true`：后台执行工作流，客户端通过 `GET /stream/{session_id}` 接收进度、增量文本、图片地址和完成事件。

MongoDB 按 `session_id` 保存会话，使“它怎么安装？”等上下文相关追问能够先被改写为完整问题再检索。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/upload` | 上传 PDF，同步执行解析、切片、Embedding 与 Milvus 入库 |
| `POST` | `/chat` | RAG 问答；通过 `is_stream` 选择同步或 SSE 模式 |
| `POST` | `/query` | 已弃用的兼容问答入口 |
| `GET` | `/stream/{session_id}` | 订阅指定会话的 SSE 事件 |
| `GET` | `/history/{session_id}` | 查询会话历史，支持 `limit` 参数 |
| `GET` | `/chat.html` | 打开内置聊天页面 |

服务启动后可访问 Swagger：`http://127.0.0.1:8001/docs`。

## 项目结构

```text
knowledge_base_0525/
├─ config/                         # LLM、Embedding、Milvus、MinerU 等配置
├─ processor/
│  ├─ import_processor/            # 文档导入 LangGraph 工作流
│  │  ├─ main_graph.py
│  │  ├─ state.py
│  │  └─ nodes/                    # 解析、图片处理、切片、Embedding、入库
│  └─ query_processor/             # RAG 查询 LangGraph 工作流
│     ├─ main_graph.py
│     ├─ state.py
│     ├─ prompt/                   # HyDE 与回答 Prompt
│     └─ nodes/                    # 问题改写、检索、RRF、重排、生成
├─ utils/                          # Milvus、MongoDB、MinIO、LLM、SSE 工具
├─ web/
│  ├─ api/query_service.py         # FastAPI 服务入口
│  └─ page/chat.html               # 内置聊天页面
├─ test/                           # 实验与接口验证脚本
├─ docker-compose.yml              # etcd、MinIO、Milvus Standalone
├─ requirements.txt
└─ .env.example
```

## 本地运行

### 1. 环境要求

- Python 3.11
- Docker Desktop / Docker Compose
- MongoDB（默认 `localhost:27017`，当前 Compose 不包含该服务）
- MinerU API Token
- OpenAI 兼容的 LLM API Key
- DashScope TextReRank 模型配置
- 本地 BGE-M3 模型，或可下载模型的网络环境

### 2. 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

根据实际环境选择 BGE-M3 的 CPU 或 CUDA 设备。使用 GPU 时需安装与本机 CUDA 匹配的 PyTorch。

### 3. 配置环境变量

重点检查 `.env` 中的以下配置；不要提交真实密钥：

```dotenv
MINERU_API_TOKEN=your-mineru-token
MINERU_BASE_URL=https://mineru.net/api/v4

OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-flash
LLM_DEFAULT_TEMPERATURE=0.1
VL_MODEL=qwen3-vl-flash

BGE_M3_PATH=./data/models/bge-m3
BGE_M3=BAAI/bge-m3
BGE_DEVICE=cpu
BGE_FP16=False

TEXT_RERANK_MODEL=your-rerank-model
TEXT_RERANK_INSTRUCT=

MILVUS_URL=http://localhost:19530
CHUNKS_COLLECTION=kb_chunks

MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=kb001

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=knowledge-base
MINIO_IMG_DIR=upload-images

UPLOAD_DIR=./data/uploads
OUTPUT_DIR=./output
```

### 4. 启动依赖与 API

```powershell
docker compose up -d
docker compose ps
python -m uvicorn web.api.query_service:app --host 127.0.0.1 --port 8001
```

请同时确认 MongoDB 已启动并监听 `.env` 中配置的地址。

## 快速体验

1. 打开 `http://127.0.0.1:8001/chat.html` 或 Swagger 页面。
2. 调用 `POST /upload` 上传 PDF，等待返回 `chunks_count`。
3. 调用 `POST /chat`：

```json
{
  "query": "这份文档主要介绍了什么？",
  "session_id": "demo-session-001",
  "is_stream": false
}
```

4. 使用相同 `session_id` 继续提问，验证多轮问题改写与上下文记忆。
5. 访问 `GET /history/demo-session-001` 查看持久化的会话记录。

> 当前 `/upload` 为同步接口，大型 PDF 的耗时取决于 MinerU 解析、图片处理、Embedding 和文档长度。

## 当前限制

- 当前主查询工作流仅使用本地知识库检索；仓库中的 Web Search 节点尚未注册到主图。
- `/upload` 会在请求内同步执行完整导入工作流，处理大型 PDF 时请求耗时较长。
- 当前 API 未提供文档列表、删除或知识库空间管理接口。
- 当前切片数据未记录页码、段落坐标等细粒度引用位置。

## 未来优化方向

- 将文档导入改造成可持久化的异步任务，并提供任务状态查询。
- 增加文档列表、删除和知识库隔离等管理能力。
- 补充页码、段落坐标等引用元数据，提升答案可追溯性。
- 建立离线评测集，评估召回、重排和回答质量。
- 完善结构化日志、健康检查、单元测试与集成测试。
- 评估将联网检索或 Agent/MCP 工具调用作为可选查询分支接入主工作流。
