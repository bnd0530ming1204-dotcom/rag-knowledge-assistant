# RAG Evaluation V2

> **SYNTHETIC / FOR EVALUATION ONLY**

This directory contains a synthetic evaluation corpus for an enterprise smart-office-device knowledge base. It is not real company data and must not be represented as such.

## Current status

`RAG_V2_COMPLETE` — the Frozen benchmark, baseline, ablations, separate
calibration/gate experiment, production promotion, and final production-node
regression are complete. Evidence Gate v1 was not promoted.

The required lifecycle is:

`DRAFT -> VALIDATED -> HUMAN REVIEW -> FROZEN`

Query text, ground truth, and reference answers are immutable. Corrections after
freezing must be recorded in `dataset/correction_log.jsonl` and produce a new
dataset version; frozen files must never be silently edited to improve metrics.

## Layout

- `documents/`: ten synthetic Markdown knowledge-base documents.
- `documents_frozen/`: immutable corpus snapshot used by the baseline.
- `dataset/dataset_v2_draft.json`: draft queries and source-grounded labels.
- `dataset/dataset_v2_frozen.json`: frozen 110-query dataset.
- `dataset/dataset_v2.schema.json`: JSON Schema.
- `dataset/correction_log.jsonl`: empty correction ledger for future frozen versions.
- `validators/validate_dataset.py`: quality, coverage, and overlap checks.
- `runners/baseline_runner.py`: current-retrieval baseline runner; does not alter runtime configuration.
- `runners/answer_eval_adapter.py`: answer-level evaluation interface only.
- `artifacts/manifest_frozen.json`: frozen hashes, counts, timestamp, and distributions.
- `artifacts/ingestion_frozen.json`: isolated ingestion receipt for `rag_eval_v2_chunks`.
- `artifacts/baseline_current_production.json`: complete per-query baseline traces.
- `artifacts/failure_analysis.json`: evidence-limited failure analysis.
- `artifacts/ablation_a1_dense.json` through `ablation_g_candidate10.json`: Phase 2 per-query experiment artifacts.
- `artifacts/phase2_derived_analysis.json`: HyDE, rerank, cutoff, rank-movement, and table-stage comparisons.
- `reports/validation_report.json`: machine-readable validator output.
- `reports/human_review_sample.md`: 25 representative cases for manual review.
- `reports/failure_taxonomy.md`: evidence-oriented failure taxonomy.
- `reports/pre_freeze_review_log.md`: objective corrections made before freezing.
- `reports/baseline_failure_report.md`: baseline failure and rank-change report.
- `reports/phase2_ablation_report.md`: Phase 2 quality/latency matrix and evidence-based recommendations.
- `reports/phase3_targeted_optimization_report.md`: final candidate, calibration/gate, failure experiments, and production decision.

Six valid source locators are intentionally not assigned to any query. They are retained as corpus distractors / unqueried knowledge rather than forcing low-value questions solely to reach 100% locator coverage.

## Commands

```bash
python evaluation_v2/validators/validate_dataset.py
python evaluation_v2/runners/baseline_runner.py --help
```

The baseline runner requires the synthetic documents to have been ingested into an isolated Milvus collection. It records results but does not claim no-answer accuracy because the production system has no evidence gate.

The current baseline used `rag_eval_v2_chunks`; it did not alter the production
collection or production retrieval settings. `NO-ANSWER DETECTION NOT IMPLEMENTED`.
