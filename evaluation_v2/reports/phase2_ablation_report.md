# RAG Evaluation V2 — Retrieval Ablation Report

Status: `ABLATION_COMPLETE`

All experiments used frozen dataset SHA-256 `6c99b11ffaa35142bc6dd3f7fd483a04fe090cfbb3210772f0db8b5cd5cd7634`, corpus manifest SHA-256 `0086b5357ff0c88cc0a5a78b660f8656d2b8814a133303a24dc4f08109ec682d`, and starting Git commit `d7a66502d980ded067b95b8572676f4961c3aa3b`.

## Quality / latency matrix

| Configuration | R@1 | R@3 | R@5 | MRR@5 | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| Dense only | .6093 | .8463 | .8796 | .7981 | 75.6 | 132.0 |
| Sparse only | .6278 | .8259 | .8833 | .7896 | 72.9 | 126.5 |
| Current Hybrid | .6537 | .8407 | .8796 | .8167 | 75.7 | 129.4 |
| Parent Heading OFF Hybrid | .6537 | .8407 | .8796 | .8167 | 78.4 | 132.5 |
| Hybrid + HyDE + RRF | .6537 | .8741 | .9019 | .8269 | 2011.9 | 2762.7 |
| + current rerank, no cutoff | .6444 | .8741 | .9019 | .8148 | 2623.0 | 3587.4 |
| Full current pipeline | .6444 | .8741 | .8907 | .8120 | 2623.1 | 3587.5 |
| Full pipeline, candidate pool 10 | .6667 | .8852 | .9278 | .8296 | 2555.2* | 3486.7* |

`*` Candidate-10 quality covers all 90 answerable queries. Latency covers 106/110 queries because DashScope returned `Arrearage` for the final four no-answer queries; it is not a complete 110-query latency sample.

## Main evidence

- Hybrid leads overall Recall@1/MRR, but Sparse leads Exact Fact and Multi-document Recall@5. Hybrid does not dominate Recall@5.
- Parent Heading ON/OFF is identical on all measured metrics. Physical Milvus auto-IDs differ; boundaries, contents and locators are identical.
- HyDE+RRF improves 4/90 first-relevant ranks, degrades 0, leaves 86 unchanged; P50 cost is about 1.88 seconds. All 20 no-answer queries generated corpus-unsupported assertions.
- Rerank improves 7 first-relevant ranks, degrades 11, and worsens aggregate Recall@1/MRR while preserving the candidate-set Recall@5.
- Cutoff removes 105 chunks and one relevant locator case (`v2q030`), lowering Recall@5 by 0.0111.
- Candidate 10 improves Multi-document Recall@5 from .75 to .85 and overall Recall@5 from .8907 to .9278, but does not complete all multi-document evidence and has an incomplete 110-query latency sample.

## Table failures

For `v2q081`, `v2q082`, and `v2q088`, relevant locator `DEPLOY-BANDWIDTH` is absent from Dense, Sparse, Hybrid, HyDE, RRF, rerank and final Top-5. The source chunk contains a valid Markdown table under `## 3 带宽规划`; failure therefore begins at initial candidate retrieval, not reranking or cutoff.

## No-answer score observations

Top-1 scores overlap substantially; no threshold is selected:

| Configuration | Relevant answerable Top-1 P50 | No-answer Top-1 P50 | No-answer range |
|---|---:|---:|---:|
| Dense | .6523 | .5845 | .5068–.7332 |
| Sparse | .2307 | .1537 | .0505–.2975 |
| Hybrid | .7732 | .7428 | .7105–.8079 |
| Full reranked baseline | .3458 | .1887 | .0464–.4196 |

There is a distribution shift, but strong overlap remains. `NO-ANSWER DETECTION NOT IMPLEMENTED`; a separate development calibration set would be required before threshold work.

## Recommended configuration (not applied)

Use current 0.8/0.2 Hybrid as the defensible base. Treat HyDE as optional because its modest gain is expensive and produces unsupported no-answer assertions. Do not retain current rerank or cliff cutoff in the recommended design based on this benchmark. Parent Heading needs more evidence. Candidate pool 10 is promising for multi-document retrieval but needs a complete latency rerun and broader validation before adoption.

