# RAG Knowledge Assistant

An evaluation-driven knowledge-base RAG project built with BGE-M3, Milvus, LangGraph, FastAPI, SSE, and MongoDB. The default retrieval path is:

```text
optional history-aware rewrite → BGE-M3 dense+sparse
→ Milvus Hybrid 0.8/0.2 → Candidate10 → Top5 → LLM answer → sources
```

HyDE, custom RRF, the current reranker, and cliff cutoff were evaluated but are not enabled by default. Parent-heading enrichment remains ingestion-compatible, although Frozen V2 measured no retrieval improvement from it.

Evaluation V2 is a **synthetic, evaluation-only** corpus: 10 documents, 110 frozen queries (90 answerable, 20 no-answer), and 39 production-ingestion chunks. The final production-node regression measured Recall@1 0.6481, Recall@3 0.8574, Recall@5 0.8944, and MRR@5 0.8204. Local wall-clock P50/P95 were 85.8/149.0 ms; these are evaluation observations, not a production SLA. Recall@3 declined from the original pipeline's 0.8741.

Evidence Gate v1 was rejected, so the system does not reliably reject no-answer queries. It also does not claim real enterprise data, page-level citations, production-scale load testing, or enterprise production readiness.

See the [main README](README.md), [engineering decisions](docs/RAG_ENGINEERING_DECISIONS.md), and [resume evidence boundaries](docs/RESUME_EVIDENCE.md) for the complete evidence.
