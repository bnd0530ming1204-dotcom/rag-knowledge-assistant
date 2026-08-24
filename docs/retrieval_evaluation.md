# Retrieval Evaluation：从 Hybrid Baseline 到 Parent Context Embedding

## 评测背景

本项目为 RAG 检索链路建立了一套独立于最终答案生成的离线评测，用于回答两个问题：相关 Chunk 是否进入 Top-K，以及首次命中是否足够靠前。评测对象是专门构造的虚构测试文档 `澄云智控平台用户手册_RAG评测版`，该文档在 Milvus 中包含 126 个真实 Chunk。

固定数据集包含 30 条经过人工式审计的 Retrieval Query，覆盖语义改写、精确关键词与型号/错误码、操作步骤、故障排查、参数与限制条件，以及确实需要多个 Chunk 才能完整回答的问题。Query 尽量采用真实用户可能提出的自然语言，而不是简单复制 Chunk 标题。

## Ground Truth 构建与审计

Ground Truth 直接依据 126 个 Chunk 的真实 `content` 建立，没有根据 Dense、Hybrid、RRF 或 Reranker 的命中结果倒推。每个相关 Chunk 保存：

- 真实 `chunk_id`；
- `file_title`；
- 用于稳定定位和人工核验的 `content_contains`；
- 仅在稳定可靠时填写的 `title`。

一个问题只有在完整回答确实需要多个 Chunk 时才标注多个 relevant chunks。标注完成后进行了专项审计：读取 Ground Truth Chunk 完整内容，检查其是否能够回答 Query、是否遗漏必要 Chunk、是否存在过度照抄或明显“送分”关键词，并通过 `--validate-only` 验证 Schema 和 Ground Truth 定位。

这仍是一套候选人工标注集。人工审计降低了自动标注偏差，但不能证明相关 Chunk 已被穷举完毕；源文档或 Chunk 发生变化时也需要重新核验 locator。

## 指标定义

对每条 Query：

\[
Recall@K = \frac{Top\text{-}K\ 中命中的不同相关\ Chunk\ 数}{Ground\ Truth\ 相关\ Chunk\ 总数}
\]

30 条 Query 的 Recall@K 是上述数值的算术平均，因此多 Chunk 问题允许部分命中。

MRR@5 取第一个相关 Chunk 在 Top-5 中排名的倒数；Top-5 无相关 Chunk 时为 0，然后对全部 Query 取算术平均。

Current Retrieval 的指标在 Rerank 排序后、动态 cutoff 前计算。动态 cutoff 仍用于项目回答上下文，但不混入本次固定 Top-5 检索指标。

## 对照方案

### Dense Only baseline

原始 Query 经 BGE-M3 生成 Dense Vector，直接在 baseline Milvus Collection 中执行 cosine Top-5 检索。该方案用于衡量不含 Sparse、HyDE、RRF 和 Reranker 时的基础语义召回能力。

### Original Hybrid Retrieval baseline

原始 Hybrid 链路组合 ordinary Dense/Sparse retrieval、HyDE Dense/Sparse retrieval、RRF fusion 和语义 Reranker，最终评估固定 Top-5。离线评测不启用依赖会话历史的 Query Rewrite。

### Parent Context Embedding

实验保留原有 126 个 Chunk，不重新解析 PDF、不重新切 Chunk，也不修改原始 `content`。它按照有序标题中的章节编号关系，为子 Chunk 通用推导最近的父级章节标题，并将 Embedding 输入增强为：

```text
parent_title

original content
```

实验 Collection 为 `kb_chunks_parent_context_v1`。它与 baseline 的 `chunk_id` 一一对应，126/126 个 `content` 完全一致，仅补充或修正 `parent_title` 并重新生成 Dense/Sparse Vector。Reranker 和最终回答上下文仍接收原始 Chunk content；Query Rewrite、HyDE Prompt、Dense/Sparse 权重、RRF、Reranker 和动态 cutoff 公式均未因该实验改变。

父级主题使高度相似的“参数规则”“异常处理”“操作步骤”等子 Chunk 获得所属模块语境，减少仅凭通用子标题或重复模板正文造成的章节混淆。

## 固定实验结果

| Experiment | Recall@1 | Recall@3 | Recall@5 | MRR@5 |
|---|---:|---:|---:|---:|
| Dense Only baseline | 0.4500 | 0.5333 | 0.6000 | 0.5611 |
| Original Hybrid baseline | 0.5167 | 0.6000 | 0.6333 | 0.6233 |
| Parent Context Embedding | 0.5500 | 0.7833 | 0.9167 | 0.7411 |

在当前固定评测集上，Parent Context Embedding 将 Current Retrieval 的 Recall@5 从 **63.33% 提升到 91.67%**，MRR@5 从 **0.6233 提升到 0.7411**。它不仅扩大了 Top-5 覆盖，在 Recall@3 上也从 0.6000 提升到 0.7833，说明更多相关 Chunk 提前进入了较靠前的位置。

## Ablation 与 Failure Analysis

第一轮将 ordinary、HyDE 和 RRF 候选池从 5 扩大到 10。更大的候选池确实救回了部分此前缺失的 Ground Truth，但新增的相似候选也干扰了 Reranker，使部分原本命中的正确 Chunk 被挤出 Top-5。最终 Recall@5 从 baseline 的 0.6333 降至 0.6167，因此该方案判定失败，不作为最终配置。

第二轮保留较大的 RRF 候选池，但限制进入 Reranker 的候选数量，以减少新增候选对最终 Top-5 的破坏。结果 Recall@5 为 0.6333，与原 baseline 持平；MRR@5 提升到 0.6500，但没有改善目标指标，因此只说明截断位置影响排序，不能解决主要召回缺口。项目随后停止简单 Top-K 参数搜索。

逐 Query 分析显示，主要失败模式不是单纯“候选数量不足”，而是 Chunk 本身缺少父级章节语境：系统可能召回同主题的主体 Chunk，却遗漏真正包含参数、限制条件、异常处理或操作步骤的 sibling Chunk；多个章节中的参数 Chunk 又具有高度相似的标题和模板内容，容易相互混淆。

Parent Context 实验救回了原始 Hybrid Top-5 完全失败的 10 条 Query 中的 8 条：`q003`、`q009`、`q016`、`q019`、`q020`、`q023`、`q027`、`q028`。`q001` 和 `q017` 仍然失败。没有为了处理这些 Query 修改 Ground Truth、Query 文本或编写基于 `chunk_id` 的定向规则。

`q001` 和 `q017` 表明 Parent Context 不是完整解决方案：自然语言表述、多个章节中近似重复的异常与参数描述，以及有限候选预算仍可能导致正确 Chunk 无法进入最终 Top-5。项目在达到本轮目标后停止继续针对固定评测集调参，避免通过定向优化放大过拟合风险。

## 结论

两轮候选池实验说明，单纯增加 Top-K 并不会稳定提高最终召回；更多噪声候选可能反而破坏 Reranker 的 Top-5。Parent Context Embedding 针对的是更上游、也更可泛化的表示问题：为子 Chunk 的向量表示补充其所属章节主题，同时保持返回内容和下游链路不变。

当前结果支持将 Parent Context 作为后续生产入库设计的候选方案，但本次实验没有修改生产入库链路，也没有把实验 Collection 直接替换为生产 Collection。正式集成仍需独立的实现、测试、版本化重建和回滚方案。

## 局限与适用边界

- 评测集只有 30 条 Query，统计规模小；
- 只覆盖一份包含 126 个 Chunk 的虚构用户手册，章节结构和重复模式具有特定性；
- Ground Truth 虽经人工式审计，仍可能存在漏标或主观判断；
- Parent Context 的编号层级推导依赖文档标题结构，非编号或层级混乱文档需要更稳健的 Markdown 标题栈和回退策略；
- HyDE LLM 与远程 Reranker 的服务版本或生成波动可能影响复跑结果；
- 本评测不衡量回答忠实度、答案完整性、引用质量、线上延迟、吞吐或成本；
- 未对其他领域、其他文档类型或生产流量验证泛化能力。

**因此，以上结果仅来自固定、小规模、虚构测试文档上的离线 Retrieval Evaluation，不是生产准确率、回答正确率或跨领域泛化指标。**

## 复现

数据校验、实验 Collection 构建、显式结果文件命名、所需环境配置和正式运行命令见 [`evaluation/README.md`](../evaluation/README.md)。结构化指标见 [`evaluation/results/metrics_summary.json`](../evaluation/results/metrics_summary.json)。
