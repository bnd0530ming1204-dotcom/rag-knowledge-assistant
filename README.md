# RAG Knowledge Assistant / 智能知识库问答系统

一个面向个人项目展示的 RAG（Retrieval-Augmented Generation，检索增强生成）知识库助手。系统支持通过 FastAPI 上传 PDF，调用 MinerU 将文档解析为 Markdown，完成文本切分与 BGE-M3 向量化后写入 Milvus；用户提问时，系统执行混合检索、RRF 融合与 Rerank 重排序，并结合 MongoDB 中保存的会话历史生成回答。

项目重点展示 AI 应用开发中的文档处理、向量检索、工作流编排、模型调用和 API 服务能力。

## 技术栈

- Python 3.11
- FastAPI + Uvicorn
- LangGraph 工作流编排
- MinerU PDF 文档解析 API
- BGE-M3 Embedding（Dense + Sparse）
- Milvus 向量数据库
- RRF（Reciprocal Rank Fusion）结果融合
- DashScope TextReRank
- OpenAI 兼容接口调用 LLM
- MongoDB 会话历史
- Docker Compose、etcd、MinIO、Milvus Standalone

## 系统架构

### 文档导入流程

```text
PDF 上传
  → 本地文件保存
  → MinerU 解析
  → Markdown
  → 图片目录缺失时跳过图片处理
  → 标题切分、长文本切分与短块合并
  → BGE-M3 Dense + Sparse Embedding
  → Milvus 建库与入库
```

### RAG 问答流程

```text
用户问题 + session_id
  → 读取 MongoDB 历史
  → 多轮问题改写
  → BGE-M3 混合检索
  → HyDE 混合检索
  → RRF 融合
  → DashScope Rerank
  → 组装检索上下文与历史对话
  → LLM 生成回答
  → MongoDB 保存回答
```

## 核心功能

- PDF 上传：通过 Swagger 或 HTTP 接口上传 PDF。
- 文档解析：调用 MinerU API 获取 Markdown 和结构化解析结果。
- 文本切分：优先按 Markdown 标题组织内容，并处理过长或过短的文本块。
- 混合向量：BGE-M3 同时生成 Dense 和 Sparse 向量。
- 向量存储：在 Milvus 中创建集合和索引，并支持同名文档幂等更新。
- 多路检索：融合普通语义检索与 HyDE 检索结果。
- Rerank：使用 DashScope TextReRank 对候选内容重新排序。
- RAG 回答：将重排后的知识片段交给 LLM 生成有依据的答案。
- 多轮会话：使用 `session_id` 从 MongoDB 读取和保存对话历史。
- API 服务：提供上传、问答、历史查询和 SSE 流式输出基础能力。

## API 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/upload` | 上传 PDF，并同步执行解析、切分、向量化和入库 |
| `POST` | `/chat` | 执行 RAG 问答，支持 `session_id` 和流式开关 |
| `POST` | `/query` | 兼容旧客户端的已弃用问答入口 |
| `GET` | `/stream/{session_id}` | 获取 SSE 流式事件 |
| `GET` | `/history/{session_id}` | 查询指定会话的历史消息 |
| `GET` | `/chat.html` | 打开项目内置聊天页面 |

启动服务后可访问 Swagger：`http://127.0.0.1:8001/docs`。

## 项目结构

```text
knowledge_base_0525/
├── config/                         # MinerU、LLM、Embedding、Milvus 等配置
├── processor/
│   ├── import_processor/           # PDF/Markdown 导入 LangGraph
│   │   ├── main_graph.py
│   │   ├── state.py
│   │   └── nodes/                  # 解析、图片跳过、切分、Embedding、入库节点
│   └── query_processor/            # RAG 查询 LangGraph
│       ├── main_graph.py
│       ├── state.py
│       ├── prompt/                 # 问题改写、HyDE 和回答提示词
│       └── nodes/                  # 检索、RRF、Rerank 和答案生成节点
├── utils/                          # Milvus、MongoDB、LLM、Embedding、SSE 工具
├── web/
│   ├── api/query_service.py        # FastAPI 应用入口
│   └── page/chat.html              # 简单聊天页面
├── data/uploads/                   # 上传文件目录（运行时创建）
├── output/                         # MinerU 与切分产物
├── volumes/                        # Docker 服务持久化数据
├── test/                           # 实验和测试脚本
├── docker-compose.yml              # etcd、MinIO、Milvus Standalone
├── requirements.txt
├── .env.example
└── README.md
```

## 环境要求

- Windows
- Python 3.11
- Docker Desktop
- MongoDB（默认 `localhost:27017`）
- 可用的 MinerU API Token
- 可用的 DashScope/OpenAI 兼容 API Key
- 本地 BGE-M3 模型，或允许下载模型的网络环境

Docker Compose 会启动 Milvus 所需的 etcd、MinIO 和 Milvus Standalone。MongoDB 不在当前 Compose 文件中，需要单独运行。

## 配置

复制示例配置：

```powershell
Copy-Item .env.example .env
```

至少需要检查以下配置：

```dotenv
MINERU_API_TOKEN=your-mineru-token
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-flash

BGE_M3_PATH=./data/models/bge-m3
BGE_M3=BAAI/bge-m3
BGE_DEVICE=cpu

TEXT_RERANK_MODEL=your-dashscope-rerank-model
TEXT_RERANK_INSTRUCT=

MILVUS_URL=http://localhost:19530
CHUNKS_COLLECTION=kb_chunks
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=kb001

UPLOAD_DIR=./data/uploads
OUTPUT_DIR=./output
```

不要将真实 API Key 提交到版本库。

## 启动方式

### 1. 创建环境并安装依赖

```powershell
cd C:\Users\<username>\AIProjects\knowledge_base_0525
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

PyTorch 的 CPU/CUDA 版本应根据本机环境选择。项目会在 CUDA 不可用时自动使用 CPU。

### 2. 准备 BGE-M3

将模型放在 `.env` 中 `BGE_M3_PATH` 指定的目录。示例配置使用 `./data/models/bge-m3`。

### 3. 启动 Milvus

```powershell
docker compose up -d
docker compose ps
```

### 4. 启动 MongoDB

确认 MongoDB 正在监听 `.env` 配置的地址，默认端口为 `27017`。

### 5. 启动 FastAPI

```powershell
python -m uvicorn web.api.query_service:app --host 127.0.0.1 --port 8001
```

开发环境可增加 `--reload`。

## 快速体验

1. 打开 `http://127.0.0.1:8001/docs`。
2. 调用 `POST /upload` 上传 PDF，等待返回 `chunks_count`。
3. 调用 `POST /chat`：

```json
{
  "query": "这份文档主要介绍了什么？",
  "session_id": "demo-session-001",
  "is_stream": false
}
```

4. 使用相同的 `session_id` 继续提问，验证多轮上下文。
5. 调用 `GET /history/demo-session-001` 查看 MongoDB 中的历史消息。

`/upload` 当前为同步处理接口，大型 PDF 的请求耗时取决于 MinerU、Embedding 和文档长度。

## 后续优化方向

- 将 PDF 导入改为后台任务，并提供可持久化的任务进度。
- 增加文档列表、删除和知识库隔离能力。
- 补充页码、段落位置等引用元数据，提高答案可追溯性。
- 建立离线评测集，量化召回率、重排效果和回答质量。
- 增加结构化日志、健康检查和集成测试。
- 完善前端上传、会话管理和引用展示体验。

