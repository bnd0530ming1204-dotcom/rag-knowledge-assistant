# Evaluation V2 Baseline Failure Report

Run: `evalv2-20260829T035251Z-b8c31249`

> Labels below are evidence-based observations, not automatically proven root causes. Uncertain cases require manual review.

Answerable failures or partial-recall cases: **13**

## Top failures

- `v2q009` (exact_fact): Recall@5=0.0000; labels=unresolved_retrieval_failure; NTP 偏差超过多少会导致证书认证失败？
- `v2q029` (paraphrase_colloquial): Recall@5=0.0000; labels=unresolved_retrieval_failure; 一代 A100 老是输错那个六位数，会被晾多久？
- `v2q030` (paraphrase_colloquial): Recall@5=0.0000; labels=rerank_regression; 二代小终端密码试三回都不对，是整台机器都不能用了吗？
- `v2q040` (paraphrase_colloquial): Recall@5=0.0000; labels=unresolved_retrieval_failure; 终端亮着在线绿点，就算会议室交付完了吗？
- `v2q081` (table): Recall@5=0.0000; labels=table_failure; A100 V2 跑双屏或 4K 时建议预留多少双向带宽？
- `v2q082` (table): Recall@5=0.0000; labels=table_failure; A200 的 1080p 推荐带宽是多少？
- `v2q088` (table): Recall@5=0.0000; labels=table_failure; A100 V1 在 1080p 模式的推荐双向带宽是多少？
- `v2q071` (multi_document): Recall@5=0.5000; labels=multi_document_incomplete, rerank_regression; 部署一台 A100 V2 做 4K 会议，需要预留多少带宽且设备侧还需满足什么录制条件？
- `v2q072` (multi_document): Recall@5=0.5000; labels=multi_document_incomplete, rerank_regression; A200 无媒体时应查哪些端口，同时它的双屏显示器有什么要求？
- `v2q073` (multi_document): Recall@5=0.5000; labels=multi_document_incomplete; 返修 A100 前，返修申请要准备什么，随工单提交的日志又应怎样保护隐私？
- `v2q076` (multi_document): Recall@5=0.5000; labels=multi_document_incomplete, rerank_regression; A100 V2 启用 EAP-TLS 后仍认证失败，除了证书内容还应检查什么时间条件？
- `v2q075` (multi_document): Recall@5=0.5000; labels=multi_document_incomplete; 会议终端部署到访客网是否可行，为什么仅显示在线还不能交付？
- `v2q065` (version_confusion): Recall@5=0.6667; labels=wrong_version_or_rank_confusion, rerank_regression; A100 V1、V2、A200 的离线升级包分别是什么？

## HyDE rank-degradation review candidates

- None observed.

## Rerank regressions

- `v2q030`: pre=2, post=4, final=None.
- `v2q032`: pre=1, post=2, final=2.
- `v2q043`: pre=1, post=2, final=2.
- `v2q044`: pre=3, post=4, final=4.
- `v2q056`: pre=1, post=2, final=2.
- `v2q063`: pre=2, post=3, final=3.
- `v2q065`: pre=1, post=2, final=2.
- `v2q071`: pre=1, post=2, final=2.
- `v2q072`: pre=1, post=2, final=2.
- `v2q076`: pre=1, post=2, final=2.
- `v2q099`: pre=1, post=2, final=2.

## Observed distribution

- multi_document_incomplete: 5
- rerank_regression: 5
- table_failure: 3
- unresolved_retrieval_failure: 3
- wrong_version_or_rank_confusion: 1

## No-answer observations

- Query count: 20
- Returned candidate counts: {3: 8, 4: 2, 5: 10}
- NO-ANSWER DETECTION NOT IMPLEMENTED; no accuracy is claimed.

## Corpus-unsupported HyDE on no-answer queries

- Assertive HyDE answers observed: 20 / 20 reviewed no-answer queries.
- These generations are unsupported by the frozen corpus. No causal retrieval-rank claim is made because no relevant locator exists.
