# RAG Knowledge Assistant

基于 BGE-M3 与 Milvus 的知识库 RAG 工程，重点展示 Hybrid Retrieval、Frozen Evaluation、组件消融、失败分析，以及检索质量与延迟之间的真实取舍。它是求职展示项目，不宣称为企业生产级系统。

## 1. Final Architecture

```text
PDF / Markdown → MinerU → Markdown → heading-aware chunking
→ parent-heading enrichment → BGE-M3 dense+sparse → Milvus

Query → optional history-aware rewrite → BGE-M3
→ Milvus Hybrid (dense/sparse 0.8/0.2) → Candidate10 → Top5
→ LLM answer → sources / SSE → MongoDB history
```

LangGraph 当前查询图只注册 `prepare_query → search_embedding → answer_output`。HyDE、custom RRF、`gte-rerank-v2` 和 cliff cutoff 保留为历史/实验模块，但不在默认链路执行。Parent-heading enrichment 为保持 ingestion representation 兼容而保留；Frozen V2 消融没有测得它带来检索提升。

FastAPI 提供 `/upload`、`/chat`、`/stream/{session_id}`、`/history` 和 `/history/{session_id}`。SSE 支持 `delta`、`final` 和结构化 `error` 终止事件。

## 2. Why This Architecture?

```text
Frozen synthetic corpus → deterministic metrics → component ablation
→ failure analysis → engineering decision → production-node regression
```

旧完整链路在本地 Frozen 测试中增加约 2.6 秒 P50；当前 reranker 降低 early ranking，cliff cutoff 删除过 relevant evidence；HyDE 只有少量尾部收益，却增加延迟并对全部 20 条 no-answer 题生成 corpus-unsupported assertions。因此这些组件没有进入默认链路。

## 3. Evaluation V2

Evaluation V2 使用明确标记为 **SYNTHETIC / FOR EVALUATION ONLY** 的智能办公设备语料，不是真实企业数据：

- 10 documents，39 个 production-ingestion chunks；
- 110 Frozen queries：90 answerable、20 no-answer；
- Dataset SHA-256：`6c99b11ffaa35142bc6dd3f7fd483a04fe090cfbb3210772f0db8b5cd5cd7634`；
- Corpus manifest SHA-256：`0086b5357ff0c88cc0a5a78b660f8656d2b8814a133303a24dc4f08109ec682d`。

Ground Truth 直接依据 source documents 标注，不使用 retriever、reranker 或 LLM retrieval output 决定 relevant locator。冻结后不允许为提高分数修改 Query/Ground Truth；客观修正必须通过 correction log 和新版本完成。

## 4. Ablation Results

以下均为同一本地 Frozen Evaluation V2 的 retrieval observation，不是生产 SLA：

| Configuration | Recall@5 | MRR@5 | P50 |
| --- | ---: | ---: | ---: |
| Dense only | 0.8796 | 0.8056 | 126.0 ms |
| Sparse only | 0.8833 | 0.7815 | 128.6 ms |
| Hybrid 0.8/0.2 | 0.8796 | 0.8167 | 129.9 ms |
| Hybrid + HyDE + RRF | 0.9019 | 0.8269 | 2011.9 ms |
| + current reranker, no cutoff | 0.9019 | 0.8148 | 2623.0 ms |
| Original full pipeline | 0.8907 | 0.8120 | 2623.1 ms |
| Final production retrieval | 0.8944 | 0.8204 | 85.8 ms* |

`*` 最后一行是本次 110/110 production-node regression 的本机实测；P95 149.0 ms。不同轮次的 wall-clock latency 受机器状态影响，不能解释为线上 SLA。

Original → Final：Recall@1 `0.6444→0.6481`、Recall@3 `0.8741→0.8574`（下降）、Recall@5 `0.8907→0.8944`、MRR@5 `0.8120→0.8204`。不能描述为所有指标全面提升。

## 5. Key Engineering Decisions

- Hybrid 0.8/0.2：保留，优势主要在 early ranking，并非每项指标都优于单路。
- Candidate10：进入默认配置，用于提高候选完整性，最终仍输出 Top5。
- HyDE：实验模块；默认关闭，尾部收益不足以抵消延迟和 unsupported assertion 风险。
- Reranker：默认移除；当前模型增加延迟且使 Recall@1/MRR 回退。
- Cliff cutoff：移除；已观察到 relevant evidence 被删除且没有验证收益。
- Parent heading：保留 ingestion 兼容，但 V2 未复现收益。
- Evidence Gate v1：不部署；Frozen no-answer rejection 55%，并误拒 15/90 answerable。
- Table normalization v1：不采用；Table 和 overall 指标均无变化。
- MMR/diversity：不加入；剩余 multi-document evidence 在 Top10 外，候选内重排不能解决。

详见 [Engineering Decisions](docs/RAG_ENGINEERING_DECISIONS.md) 与 [Phase 3 Report](evaluation_v2/reports/phase3_targeted_optimization_report.md)。

## 6. Failure Analysis & Reliability

已观察到的失败包括 multi-document evidence 不完整、Markdown 表格行列语义召回不足、HyDE 无依据断言、rerank regression，以及旧 Milvus 异常可能被误当成空结果。

当前将真实空结果 `[]` 与基础设施错误分开：embedding、Milvus 和 retrieval 异常分别映射为 `EmbeddingUnavailable`、`VectorDatabaseUnavailable`、`RetrievalFailed`；FastAPI 返回脱敏 503，SSE 发出结构化 `error` 后终止。Query rewrite 失败仍 fallback 到 original query。

## 7. Quick Start

验证环境为 Python 3.11.9，关键直接依赖版本记录在 `requirements.txt`。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d
.\.venv\Scripts\uvicorn.exe web.api.query_service:app --host 127.0.0.1 --port 8001
```

在 `.env` 配置 MinerU、LLM、BGE-M3、Milvus、MongoDB 与 MinIO。`.env`、模型、缓存和数据库 volumes 均被 Git 忽略。Docker Compose clean-start 覆盖 Milvus、etcd、MinIO、MongoDB；API 不强行容器化。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_final*.py" -v
.\.venv\Scripts\python.exe evaluation_v2/runners/production_regression_runner.py `
  --collection rag_eval_v2_chunks `
  --output evaluation_v2/artifacts/final_production_regression.json
```

评测 collection 必须与开发/生产 collection 隔离。详见 [Evaluation V2 README](evaluation_v2/README.md)。

## 8. Limitations

- 评测语料为 synthetic，不能代表真实企业流量或生产规模。
- Evidence Gate v1 未部署；系统不能可靠拒绝 no-answer 问题，也不能声称解决 hallucination。
- source metadata 有 document/file、chunk、title，但没有可靠 page-level citation。
- Frozen V2 未测得 parent-heading enrichment 的收益。
- Table retrieval 仍不完善；简单 table normalization 没有改善指标。
- 未进行 production-scale load test、线上 SLA、HA 或 Kubernetes 验证。
- 外部 MinerU/LLM API 依赖凭据、额度和网络；最终 smoke 中外部回答/改写 LLM 使用 mock，retrieval/Milvus/Mongo 为真实服务。

## 9. Repository Map

```text
config/                       runtime configuration
processor/import_processor/   ingestion LangGraph
processor/query_processor/    production query graph + optional experiments
evaluation_v2/                frozen corpus, dataset, runners, artifacts, reports
test/                         acceptance tests and legacy scripts
docs/                         decision record and resume boundaries
web/api/                      FastAPI + SSE endpoints
docker-compose.yml            Milvus, etcd, MinIO, MongoDB
```

旧 30-query / 单文档 Parent Context 结果只作为 **Legacy Development Experiment** 保留，不能与 Frozen V2 直接比较，也不能用于声称 V2 的 Parent Context 提升。
