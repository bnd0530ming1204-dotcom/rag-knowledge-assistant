# Retrieval Evaluation — Legacy Development Experiment

> This 30-query, single-document evaluation is retained for historical development evidence only. It helped identify missing parent-heading context, but it is **not** the RAG Evaluation V2 Frozen Benchmark and must not be presented as one.

本目录提供与在线问答流程隔离的离线 Retrieval Evaluation 工具。评测不会调用最终回答生成节点，也不会把评测 Query 写入聊天历史。当前固定评测集包含 30 条人工审计 Query，Ground Truth 来自文档 `澄云智控平台用户手册_RAG评测版` 在 Milvus 中的 126 个真实 Chunk。

完整实验说明、指标对比和失败案例见 [`docs/retrieval_evaluation.md`](../docs/retrieval_evaluation.md)。结构化指标摘要见 [`results/metrics_summary.json`](results/metrics_summary.json)。

## 目录内容

- `dataset.json`：30 条带 Ground Truth 的评测 Query。
- `dataset.schema.json`：评测集 JSON Schema。
- `evaluate_retrieval.py`：Ground Truth 定位校验、Dense Only 与 Current Retrieval 评测。
- `inspect_chunks.py`：只读检查 Milvus 中的真实 Chunk。
- `build_parent_context_collection.py`：从 baseline Chunk 构建隔离的 Parent Context 实验 Collection。
- `results/parent_context_v1.json`：Parent Context 正式评测的完整逐 Query 产物。
- `results/parent_context_samples.json`：10 个 Parent Context 推导样本，便于人工审计。
- `results/round2_rrf10_rerank5.json`：第二轮 RRF 10 / Rerank 5 实验的完整逐 Query 历史产物。
- `results/metrics_summary.json`：已经真实运行并确认的实验指标汇总，以及完整产物是否留存的说明。

## Dataset 格式

`dataset.json` 顶层包含 `dataset_status`、`dataset_description` 和 `cases`。每个 Case 包含唯一 `id`、自然语言 `query`、问题类型 `tags` 以及一个或多个 `relevant_chunks`：

```json
{
  "id": "q001",
  "query": "用户可能提出的自然语言问题",
  "tags": ["troubleshooting", "semantic_paraphrase"],
  "relevant_chunks": [
    {
      "chunk_id": "真实 Milvus chunk_id",
      "file_title": "澄云智控平台用户手册_RAG评测版",
      "title": "仅在稳定可靠时填写",
      "content_contains": "来自 Chunk 的连续原文定位片段"
    }
  ]
}
```

Ground Truth 同时保留 `chunk_id` 和内容定位信息，便于审计。它必须独立于被评测系统建立，不能根据 Dense、Hybrid 或 Reranker 的输出倒推或修改。

## 仅校验 Dataset 和 Ground Truth

以下命令只做 Schema、状态和 Ground Truth Chunk 定位校验，不执行 Retrieval：

```bash
python evaluation/evaluate_retrieval.py --validate-only
```

## 构建 Parent Context 实验 Collection

下面的脚本读取 baseline Collection 中已有的 126 个 Chunk，通过有序标题的章节编号关系推导 `parent_title`，使用 `parent_title + original content` 重新生成 Dense/Sparse Vector，并写入独立 Collection `kb_chunks_parent_context_v1`：

```bash
python evaluation/build_parent_context_collection.py \
  --file-title "澄云智控平台用户手册_RAG评测版" \
  --experiment-collection kb_chunks_parent_context_v1
```

安全约束：

- 脚本拒绝覆盖 baseline Collection；
- 实验 Collection 已存在时脚本会退出，不会覆盖；
- 原 `chunk_id`、`title`、`content`、`file_title` 保持不变；
- 脚本不读取 `dataset.json`、Query 或 Ground Truth；
- 写入后验证 126 个 Chunk、ID 一一对应及 content 完全一致。

## 正式评测命令

Original Hybrid baseline 使用同一个 baseline Collection：

```bash
python evaluation/evaluate_retrieval.py \
  --dense-collection kb_chunks \
  --current-collection kb_chunks \
  --output evaluation/results/original_hybrid_baseline.json
```

Parent Context 实验保持 Dense Only baseline 不变，仅让 Current Retrieval 使用实验 Collection：

```bash
python evaluation/evaluate_retrieval.py \
  --dense-collection kb_chunks \
  --current-collection kb_chunks_parent_context_v1 \
  --output evaluation/results/parent_context_v1.json
```

显式指定 `--output`，避免继续用默认的 `results/latest.json` 作为长期实验名称。正式运行会调用外部 HyDE LLM 和 Reranker；应在确认数据发送范围、服务可用性和调用成本后执行。

## 运行配置

运行前需要在本地 `.env` 配置：

- Milvus：`MILVUS_URL`，baseline Collection 配置应指向 `kb_chunks`；
- BGE-M3：`BGE_M3_PATH`、`BGE_M3`、`BGE_DEVICE`、`BGE_FP16`；
- HyDE LLM：`OPENAI_API_BASE`、`OPENAI_API_KEY`、`LLM_DEFAULT_MODEL`、`LLM_DEFAULT_TEMPERATURE`；
- Reranker：`OPENAI_API_KEY`、`TEXT_RERANK_MODEL`、`TEXT_RERANK_INSTRUCT`。

变量的实际取值取决于本地模型和外部服务部署。不要向 Git 提交 `.env`、API Key、访问令牌或包含凭据的日志。

## 指标口径

- Recall@K：每条 Query 在 Top-K 中命中的不同 Ground Truth Chunk 数，除以该 Query 的 Ground Truth Chunk 总数，再对 30 条 Query 取算术平均。
- MRR@5：第一个相关 Chunk 在 Top-5 内排名的倒数；Top-5 未命中记为 0，再对 30 条 Query 取算术平均。
- Current Retrieval 指标在 Rerank 排序之后、动态 cutoff 之前计算，避免把候选检索能力与回答上下文裁剪策略混为一个指标。
- Query Rewrite 在这组无会话上下文的离线评测中关闭；Current Retrieval 保留 ordinary hybrid、HyDE hybrid、RRF 和 Reranker。

## 复现边界

该结果来自固定、小规模、虚构测试文档上的离线 Retrieval Evaluation，不是生产准确率、回答正确率或跨领域泛化指标。外部 HyDE LLM、Reranker 服务或模型版本变化也可能带来运行波动。
