# Resume Evidence and Interview Boundaries

## A. Safe Resume Claims

- 构建并冻结 110 条 synthetic Evaluation V2（90 answerable / 20 no-answer、10 documents），用 SHA-256 固定 Dataset 与 corpus manifest。
- Ground Truth 直接依据 source documents 标注，并实现唯一性、locator、coverage、近重复与 lexical-overlap validator。
- 对 Dense、Sparse、Hybrid、Parent Heading、HyDE、Rerank、cutoff 和 candidate budget 做组件级消融与逐 Query artifact 记录。
- 依据 Frozen 实验将默认链路简化为 BGE-M3 Hybrid 0.8/0.2、Candidate10、Top5；HyDE/rerank/cutoff 不默认启用。
- 区分 Milvus 真空结果和基础设施错误，并为 FastAPI/SSE 增加脱敏结构化错误及流式终止测试。
- 用真实 BGE-M3 + 隔离 Milvus collection 完成 110-query production-node regression，并建立 Mongo integration test。
- 用真实 `gte-rerank-v2` 完成 110-query rerank promotion evaluation，用真实 `qwen-flash` 完成 38-query Targeted HyDE 与 110-query generation evaluation；保留负面结果并未改变默认链路。
- 对 Generation 的 deterministic/reference-based proxy 与 10 高分、10 低分、5 no-answer 人工抽查进行一致性审计，发现 proxy 误判与假图片 URL 风险，因此只将指标用于诊断。

## B. Metrics

最终 V3 production-default regression：Recall@1 `0.6481`、Recall@3 `0.8574`、Recall@5 `0.8944`、MRR@5 `0.8204`；110/110 完整样本，本地 P50 `75.89 ms`、P95 `120.85 ms`。延迟是单机 wall-clock observation，不是 production SLA。

Generation diagnostic/reference-based proxies：answer correctness `0.7333`、faithfulness `0.5477`、source/citation coverage `0.9111`、context relevance `0.2300`；no-answer 为 supported refusal `14/20`、unsupported factual claim `5/20`、needs review `1/20`。不得称为人工准确率、语义准确率或 ground-truth production accuracy。

原始完整链路：Recall@1 `0.6444`、Recall@3 `0.8741`、Recall@5 `0.8907`、MRR@5 `0.8120`，P50 `2623.1 ms`、P95 `3587.5 ms`。必须同时说明 Recall@3 下降；延迟只是本地 evaluation observation，不是 production SLA。

## C. Ablation Results

- Hybrid：保留，主要改善 early ranking；Recall@5 不优于 Sparse。
- HyDE：V2 历史全链路实验曾有 4/90 改善；最终 V3 targeted 18-answerable subset 为 2 改善、1 降级、15 不变，HyDE generation P50 `1305.94 ms`，20/20 no-answer hypotheses 人工检查均存在 unsupported concrete assertions；默认关闭。
- Current reranker：最终 V3 真实 B 实验 Recall@1 `0.6481→0.6667`、Recall@5 `0.8944→0.9056`、MRR@5 持平 `0.8204`；8 改善、9 降级、73 不变，paired total-latency P50 overhead proxy 约 `603 ms`，且 `v2q030` relevant evidence 跌出 Top5；默认关闭、保留 optional。
- Explicit RRF：Recall@5 `0.8944→0.9056`，但 Recall@1 `0.6481→0.6389`、MRR@5 `0.8204→0.8065` 且延迟增加；默认关闭。
- Dynamic Selector：冻结参数下 context 数与 tokens 未减少；默认关闭。
- Cliff cutoff：删除过 relevant locator；默认移除。
- Parent Heading：Frozen V2 ON/OFF 指标一致；只保留兼容性。
- Evidence Gate v1：Frozen rejection 55%，15/90 false rejects；不部署。

## D. Engineering Decisions

面试回答应采用 `Problem → Evidence → Experiment → Result → Trade-off → Decision`，证据来源为 `evaluation_v2/artifacts/` 与 `docs/RAG_ENGINEERING_DECISIONS.md`，不把单次实验包装成普遍规律。

## E. Failure Stories

- Milvus 异常曾返回 `None` 并可能被当成无答案；修复为 typed retrieval error，并覆盖 HTTP/SSE 行为测试。
- Multi-document 剩余失败的 missing locator 不在 Top10，因而拒绝无证据地加入 MMR。
- Markdown table 的二维关系没有被简单 header:value normalization 改善，因此撤回候选而非继续刷 Frozen test。
- HyDE 对 no-answer 生成断言且收益集中于少数尾部 Query，故保留实验代码但移出默认路径。

## F. Interview Boundaries

可以说“在本地 Frozen synthetic benchmark 上观察到”；不能说：

- “生产延迟降低 97%”或达到生产 SLA；
- “解决 RAG hallucination / no-answer”；
- “Parent Context 提升 Recall 28%”（仅属于不可直接比较的旧开发实验，V2 未复现）；
- “企业生产系统 / 企业真实数据”；
- “所有 retrieval 指标全面提升”（Recall@3 实际下降）；
- “可靠 page-level citation”或“production-scale load tested”。
- “Generation proxy 等于人工/语义/生产准确率”或“citation coverage 等于逐 claim citation entailment”；
- “Rerank、RRF、HyDE 或 Dynamic Selector 已被证明全面优于默认链路”。
