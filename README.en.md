# RAG Knowledge Assistant

A knowledge-base assistant built with **FastAPI, LangGraph, BGE-M3, and Milvus**. It supports PDF ingestion, dense/sparse hybrid retrieval, conversation history, SSE streaming, and an evaluation-driven retrieval design validated with a frozen dataset and component ablations.

> This is an AI application engineering portfolio project. It does not claim enterprise production-grade readiness.

## Demo

### PDF Upload and Knowledge-Base Ingestion

<img alt="PDF upload and knowledge-base ingestion" height="450" src="docs/images/upload.png" width="300"/>

### RAG Chat, Answers, and Sources

<img alt="RAG chat interface" height="700" src="docs/images/chat.png" width="900"/>

<img alt="RAG answer and structured sources" height="800" src="docs/images/chatresult.png" width="950"/>

### Conversation History

<img alt="MongoDB-backed conversation history" height="400" src="docs/images/history.png" width="350"/>

### Demo Video

[View the complete running demo](https://github.com/bnd0530ming1204-dotcom/rag-knowledge-assistant/releases/tag/v1.0.0)

## Features

- PDF/Markdown ingestion with MinerU, Markdown processing, and heading-aware chunking.
- BGE-M3 dense and sparse vectors with Milvus Hybrid Retrieval at 0.8/0.2.
- MongoDB conversation history and history-aware query rewriting with original-query fallback.
- FastAPI upload, chat, history, and SSE endpoints.
- Incremental SSE deltas, final answers with structured sources, and structured error termination.
- Typed handling for embedding, vector-database, and retrieval failures; an infrastructure error is never treated as a normal empty result.
- Frozen evaluation, ablation, and regression artifacts used to justify retrieval decisions.

## Architecture

```text
Document:
PDF / Markdown → MinerU / Markdown processing → heading-aware chunking
→ parent-heading enrichment → BGE-M3 dense+sparse → Milvus

Query:
Query → optional history-aware rewrite → Hybrid Retrieval 0.8/0.2
→ Candidate10 → Top5 Context → LLM → Answer + Sources / SSE
```

Parent-heading enrichment is retained for ingestion compatibility, but Frozen V2 measured no retrieval improvement from it. Earlier versions evaluated HyDE, custom RRF, and reranking; they remain available as experimental/history modules but are disabled in the default query graph after ablation. Cliff cutoff was removed.

## Why This Is More Than a Basic RAG Demo

1. A 110-query synthetic benchmark is frozen with dataset and corpus hashes.
2. Dense, Sparse, Hybrid, Parent Heading, HyDE, Rerank, cutoff, and candidate budget were evaluated independently.
3. Decisions report Recall@K, MRR@5, and wall-clock latency—including regressions such as lower Recall@3.
4. Retrieval no-result and retrieval infrastructure failure have different API/SSE behavior.

## Evaluation

Evaluation V2 is explicitly **SYNTHETIC / FOR EVALUATION ONLY**: 10 documents, 110 frozen queries (90 answerable, 20 no-answer), and 39 production-ingestion chunks.

| Metric | Original full pipeline | Final default pipeline |
| --- | ---: | ---: |
| Recall@1 | 0.6444 | 0.6481 |
| Recall@3 | **0.8741** | **0.8574 ↓** |
| Recall@5 | 0.8907 | 0.8944 |
| MRR@5 | 0.8120 | 0.8204 |
| Retrieval P50 | 2623.1 ms | 85.8 ms* |

`*` Local frozen-evaluation wall-clock observation, not a production SLA. Recall@3 declined, so these results must not be described as across-the-board metric improvement.

Details: [Phase 2 Ablation](evaluation_v2/reports/phase2_ablation_report.md), [Phase 3 Report](evaluation_v2/reports/phase3_targeted_optimization_report.md), and [Engineering Decisions](docs/RAG_ENGINEERING_DECISIONS.md).

## Key Engineering Decisions

- **Hybrid: keep.** It improved early ranking, although it did not win every metric.
- **Candidate10: keep.** Retrieve a wider pool, then pass only Top5 to answer generation.
- **HyDE: disabled by default.** Its tail-query gains did not justify latency and unsupported assertions on no-answer prompts.
- **Current reranker: disabled by default.** It added remote latency and regressed Recall@1/MRR.
- **Cliff cutoff: removed.** It deleted relevant evidence without a validated benefit.
- **Evidence Gate v1: not deployed.** Frozen-test false rejection was unacceptable; the system does not claim reliable no-answer detection.

## Quick Start

Requirements: Python 3.11, Docker Compose, MinerU and OpenAI-compatible API credentials, and BGE-M3 locally or through an available model download.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d
.\.venv\Scripts\uvicorn.exe web.api.query_service:app --host 127.0.0.1 --port 8001
```

Open `http://127.0.0.1:8001/chat.html` for the bundled UI or `http://127.0.0.1:8001/docs` for Swagger. Upload a PDF through the UI or `POST /upload`, then call `POST /chat` with a stable `session_id`.

```json
{
  "query": "What is this document mainly about?",
  "session_id": "demo-session-001",
  "is_stream": true
}
```

Run acceptance tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_final*.py" -v
```

## Limitations

- The evaluation corpus is synthetic and does not represent real enterprise traffic or production scale.
- Evidence Gate v1 is not deployed; no-answer queries are not reliably rejected.
- Sources do not provide reliable page-level metadata.
- Frozen V2 did not reproduce a parent-heading retrieval gain.
- Markdown-table retrieval remains imperfect.
- No production-scale load test, online SLA, HA, or Kubernetes claim is made.
- External MinerU/LLM availability depends on network access, credentials, and quota.
