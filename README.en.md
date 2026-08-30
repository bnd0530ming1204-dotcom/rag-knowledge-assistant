# RAG Knowledge Assistant

## Overview

An end-to-end RAG knowledge-base assistant built with **Python, FastAPI, and LangGraph**. It supports PDF/Markdown parsing and ingestion, multi-turn conversations, query rewriting, BGE-M3 dense+sparse hybrid retrieval, context construction, streaming LLM generation, and source tracking. Milvus manages vector retrieval, MongoDB stores conversation history, and structured errors, fallbacks, and request traces improve observability and application stability.

## Demo

### Document Upload and Knowledge-Base Ingestion

<img alt="PDF upload and knowledge-base ingestion" height="450" src="docs/images/upload.png" width="300"/>

### Knowledge QA

<img alt="RAG chat interface" height="700" src="docs/images/chat.png" width="900"/>

### Answer + Sources

<img alt="RAG answer and structured sources" height="800" src="docs/images/chatresult.png" width="950"/>

### Conversation History

<img alt="MongoDB-backed conversation history" height="400" src="docs/images/history.png" width="350"/>

### Demo Video

[View the complete running demo in the GitHub Release](https://github.com/bnd0530ming1204-dotcom/rag-knowledge-assistant/releases/tag/v1.0.0)

## Core Features

- PDF / Markdown ingestion with MinerU parsing
- Heading-aware / hierarchical chunking and parent metadata
- BGE-M3 dense and sparse embeddings
- Milvus Weighted Hybrid Retrieval
- Conditional / history-aware query rewriting with original-query fallback
- Configurable Explicit RRF, Rerank, HyDE Router, and Fixed / Dynamic Context Selectors
- Context deduplication, same-parent control, and token budgets
- qwen-flash answer generation with structured sources
- Incremental SSE `delta → final/error → close`
- MongoDB conversation history
- Structured errors, reliability fallbacks, and request traces

## System Architecture

The application combines a document knowledge pipeline, an online query pipeline, and supporting infrastructure. Documents are parsed, chunked, embedded, and stored in Milvus; queries use conversation history for retrieval and context construction before streaming an answer with sources; MongoDB, SSE, and request traces manage state and runtime visibility.

## Document Pipeline

```text
PDF / Markdown
→ MinerU / Markdown Processing
→ Cleaner
→ Heading-aware / Hierarchical Chunking
→ Metadata / Parent Heading
→ BGE-M3 Dense + Sparse Embeddings
→ Milvus
```

## Query Pipeline

```text
User Query
→ MongoDB History
→ History-aware Rewrite
→ BGE-M3 Dense + Sparse Retrieval
→ Weighted Hybrid 0.8 / 0.2
→ Candidate10
→ Fixed Top5 Context Builder
→ qwen-flash
→ Answer + Structured Sources
→ SSE Streaming
→ MongoDB History
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Application | Python 3.11, FastAPI, LangGraph |
| Document Processing | MinerU, Markdown |
| Embedding | BGE-M3 Dense + Sparse |
| Retrieval | Milvus, Weighted Hybrid, optional RRF / Rerank / HyDE |
| Generation | DashScope, qwen-flash |
| History | MongoDB |
| Streaming | Server-Sent Events |
| Infrastructure | Docker Compose, Milvus, MinIO, etcd, MongoDB |

## Engineering Design & Reliability

- Typed structured errors for embedding, Milvus, and generation failures
- Query Rewrite failure falls back to the original query
- HyDE / Rerank failure falls back to base retrieval results
- Mongo read failure enters stateless mode; write failure preserves a successful answer
- SSE terminal states: `COMPLETED / FAILED / TIMEOUT / CANCELLED`
- Request traces for strategy, candidates, context tokens, latency, fallbacks, and errors
- Context token budgets, metadata normalization, and source deduplication
- Docker Compose for Milvus, MinIO, etcd, and MongoDB

## Retrieval Optimization & Engineering Decisions

For semantic matching, keyword matching, and complex query scenarios, the project compares Dense, Sparse, Weighted Hybrid, Explicit RRF, Rerank, HyDE, and Context Selection strategies, then selects the default path using retrieval quality, latency, and runtime stability.

- 110-query evaluation set (90 answerable / 20 no-answer)
- 10 synthetic evaluation documents with dataset and corpus hash freeze
- Real BGE-M3, Milvus, `gte-rerank-v2`, and `qwen-flash` runs

Final retrieval and generation path:

```text
History-aware Rewrite
→ BGE-M3 Weighted Hybrid 0.8 / 0.2
→ Candidate10
→ Fixed Top5
→ qwen-flash
```

## Core Results

| Final Retrieval Metric | Result |
| --- | ---: |
| Recall@1 | 0.6481 |
| Recall@3 | 0.8574 |
| Recall@5 | 0.8944 |
| MRR@5 | 0.8204 |
| Retrieval / Context P50 | 75.89 ms |
| Retrieval / Context P95 | 120.85 ms |

| Verification | Result |
| --- | ---: |
| Automated tests | 66 passed, 0 failed |
| Real Milvus integration | PASS |
| Real MongoDB integration | PASS |

## Quick Start

Requirements: Python 3.11, Docker Desktop / Docker Compose, available MinerU and OpenAI-compatible LLM APIs, and BGE-M3 locally or through an available model download.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d
docker compose ps
.\.venv\Scripts\uvicorn.exe web.api.query_service:app --host 127.0.0.1 --port 8001
```

- Chat UI: `http://127.0.0.1:8001/chat.html`
- Swagger: `http://127.0.0.1:8001/docs`

Run acceptance tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s test -p "test_final*.py" -v
```

## Project Structure

```text
config/                 Application and retrieval settings
processor/              Ingestion and query-graph nodes
utils/                  Embedding, Milvus, Mongo, context, and reliability utilities
web/                    FastAPI APIs and bundled Chat UI
evaluation_v2/          Frozen dataset and historical experiment artifacts
evaluation_v3/          Final strategy, generation, and regression artifacts
test/                   Unit, acceptance, and integration tests
docs/                   Engineering decisions, resume evidence, and Demo assets
```

## Technical Reports

- [RAG V3 Final Report](evaluation_v3/reports/RAG_V3_FINAL_REPORT.md)
- [RAG Engineering Decisions](docs/RAG_ENGINEERING_DECISIONS.md)
- [Resume-safe Evidence](docs/RESUME_EVIDENCE.md)
- [Evaluation V2 and Artifacts](evaluation_v2/README.md)
