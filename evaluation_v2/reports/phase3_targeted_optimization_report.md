# RAG Evaluation V2 — Phase 3 Targeted Optimization

Status: `TARGETED_OPTIMIZATION_COMPLETE`

## Final evaluation-only candidate

`BGE-M3 -> Hybrid 0.8/0.2 -> candidate budget 10 -> final Top5`; HyDE, rerank and cliff cutoff OFF. Parent-heading ingestion remains compatible, with no V2 improvement claim.

| Metric | Original full baseline | Final candidate | Delta |
|---|---:|---:|---:|
| Recall@1 | .6444 | .6481 | +.0037 |
| Recall@3 | .8741 | .8574 | -.0167 |
| Recall@5 | .8907 | .8944 | +.0037 |
| MRR@5 | .8120 | .8204 | +.0083 |
| P50 | 2623.1 ms | 80.9 ms | -2542.2 ms |
| P95 | 3587.5 ms | 213.9 ms | -3373.6 ms |

All 110 queries completed without DashScope. Category Recall@5: Exact .9667, Paraphrase .8333, Parent 1.0, Version .9583, Multi-document .80, Table .625.

## Evidence Gate

Separate dataset: `DEVELOPMENT CALIBRATION ONLY`, 40 queries (20 answerable / 20 no-answer), SHA-256 `664d92d3eb60b7f990c22cd19c4257972f89e18d9237a295b655618c5713460a`. No exact Frozen duplicate; maximum character similarity .7442 after replacing one risky near duplicate before final calibration.

Locked rule: accept only when Hybrid Top1 score >= .75. Score is treated as a ranking signal, not probability. Margin rules were examined on calibration but reduced recall and were not selected.

| Set | Accept precision | Answerable accept recall | No-answer rejection | False accept | False reject |
|---|---:|---:|---:|---:|---:|
| Development calibration | .80 | .80 | .80 | 4 | 4 |
| Frozen Test, one locked-rule run | .8929 | .8333 | .55 | 9 | 15 |

On rejection, generation is skipped and the response is `NO_SUFFICIENT_EVIDENCE` / `当前知识库中没有足够证据支持该问题。` Candidate metadata may be returned only as `not enough evidence`.

The gate is not production-ready: Frozen score overlap yields 45% no-answer false accepts and 16.7% answerable false rejects. Frozen outcomes were not used to retune it.

## Targeted failures

- Multi-document: remaining misses (`v2q071`, `v2q073`, `v2q076`) lack one relevant locator throughout Top10. Same-document crowding is not the proven cause; MMR/diversity was not added.
- Table: `DEPLOY-BANDWIDTH` remains outside Top10 for `v2q081`, `v2q082`, `v2q088`. Generic Markdown header:value serialization was tested in an isolated collection while preserving original context. Overall and Table metrics were exactly unchanged, so the change is rejected.

## Reliability and trace

The evaluation path distinguishes `EmbeddingUnavailable`, `VectorDatabaseUnavailable`, `RetrievalFailed`, and `EvidenceInsufficient`. A real Milvus-unloaded failure exposed the old `None -> []` ambiguity; the Phase 3 runner now loads the collection and raises on the error sentinel instead of calling it no-result.

Structured trace contains 110 rows with run/query/config, embedding and Milvus latency, candidate count, top document/score, gate result, total latency, error and fallback. HyDE fields are present and false/null for the default candidate.

## Production decision

No production promotion was made. The retrieval candidate is strong enough for continued evaluation, but the Evidence Gate failed the reliability bar and no predeclared acceptance threshold existed. Production acceptance and FastAPI/SSE/Mongo smoke tests therefore remain pending rather than being falsely reported as passed.

