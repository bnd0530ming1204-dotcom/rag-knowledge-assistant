"""Run the current production retrieval configuration against Evaluation V2.

This module records the existing behavior. It does not tune weights, candidate
limits, Parent Context, HyDE, RRF, or reranking. The draft dataset must be
explicitly allowed; draft runs are never called a final benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATASET = EVAL_ROOT / "dataset" / "dataset_v2_draft.json"
MANIFEST_DRAFT = EVAL_ROOT / "artifacts" / "manifest_draft.json"
MANIFEST_FROZEN = EVAL_ROOT / "artifacts" / "manifest_frozen.json"
OUTPUT_FIELDS = ["chunk_id", "content", "title", "file_title", "parent_title"]


def timed(stage: str, fn, traces: list[dict[str, Any]]):
    started = time.perf_counter()
    error = None
    fallback = False
    try:
        value = fn()
        return value
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        traces.append({
            "stage": stage,
            "latency_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": error,
            "fallback": fallback,
        })


def entity(hit: Any) -> dict[str, Any]:
    if isinstance(hit, dict):
        raw = hit.get("entity") or hit
        score = hit.get("distance", hit.get("score"))
    else:
        raw = getattr(hit, "entity", {}) or {}
        score = getattr(hit, "distance", None)
    doc = dict(raw)
    doc["score"] = float(score) if score is not None else None
    doc["chunk_id"] = str(doc.get("chunk_id", ""))
    return doc


def locators_in(doc: dict[str, Any]) -> list[str]:
    import re
    return re.findall(r"<!-- locator: ([A-Z0-9-]+) -->", str(doc.get("content", "")))


def printable(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for rank, doc in enumerate(docs, 1):
        rows.append({
            "rank": rank,
            "chunk_id": str(doc.get("chunk_id", "")),
            "document_id": str(doc.get("file_title", "")).upper(),
            "file_title": doc.get("file_title", ""),
            "title": doc.get("title", ""),
            "locators": locators_in(doc),
            "score": doc.get("score"),
            "content_preview": str(doc.get("content", ""))[:300],
        })
    return rows


def metrics(docs: list[dict[str, Any]], relevant: list[str]) -> dict[str, float | int | None]:
    if not relevant:
        return {"recall@1": 0.0, "recall@3": 0.0, "recall@5": 0.0, "mrr@5": 0.0, "first_relevant_rank": None}
    per_rank = [set(locators_in(doc)) for doc in docs]
    relevant_set = set(relevant)
    result: dict[str, float | int | None] = {}
    for k in (1, 3, 5):
        found = set().union(*per_rank[:k]) if per_rank[:k] else set()
        result[f"recall@{k}"] = len(found & relevant_set) / len(relevant_set)
    first = next((rank for rank, found in enumerate(per_rank[:5], 1) if found & relevant_set), None)
    result["mrr@5"] = 1.0 / first if first else 0.0
    result["first_relevant_rank"] = first
    return result


def retrieve(query: str, collection: str, traces: list[dict[str, Any]], candidate_limit: int = 5) -> dict[str, Any]:
    from config.retrieval_config import retrieval_config
    from processor.query_processor.nodes.c_node_search_embedding_hyde import NodeSearchEmbeddingHyde
    from processor.query_processor.nodes.e_node_rrf import NodeRrf
    from processor.query_processor.nodes.f_node_rerank import NodeRerank
    from utils.embedding_utils import generate_embeddings
    from utils.milvus_utils import create_hybrid_search_requests, get_milvus_client, hybrid_search

    total_started = time.perf_counter()
    client = get_milvus_client()
    ordinary_started = time.perf_counter()
    embedded = timed("ordinary_embedding", lambda: generate_embeddings([query]), traces)
    reqs = create_hybrid_search_requests(
        embedded["dense"][0], embedded["sparse"][0],
        limit=candidate_limit,
    )
    ordinary_raw = timed("ordinary_hybrid", lambda: hybrid_search(
        client, collection, reqs, ranker_weights=(0.8, 0.2),
        limit=candidate_limit, output_fields=OUTPUT_FIELDS,
    ), traces)
    ordinary = [entity(hit) for hit in (ordinary_raw[0] if ordinary_raw else [])]
    traces.append({"stage": "ordinary_total", "latency_ms": round((time.perf_counter() - ordinary_started) * 1000, 3), "error": None, "fallback": False, "candidate_count": len(ordinary)})

    hyde_node = NodeSearchEmbeddingHyde()
    hyde_doc = timed("hyde_generation", lambda: hyde_node._step_1_create_embedding_hyde_doc(query), traces)
    hyde_retrieval_started = time.perf_counter()
    hyde_embeddings = timed("hyde_embedding", lambda: generate_embeddings([query + " " + hyde_doc]), traces)
    hyde_reqs = create_hybrid_search_requests(
        hyde_embeddings["dense"][0], hyde_embeddings["sparse"][0],
        limit=candidate_limit,
    )
    hyde_raw = timed("hyde_hybrid", lambda: hybrid_search(
        client, collection, hyde_reqs,
        limit=candidate_limit,
        output_fields=["chunk_id", "content", "title", "file_title"],
    ), traces)
    hyde = [entity(hit) for hit in (hyde_raw[0] if hyde_raw else [])]
    traces.append({"stage": "hyde_retrieval_total", "latency_ms": round((time.perf_counter() - hyde_retrieval_started) * 1000, 3), "error": None, "fallback": False, "candidate_count": len(hyde)})

    rrf_inputs = [(ordinary, 1.0), (hyde, 1.0)]
    rrf_pairs = timed("rrf", lambda: NodeRrf()._rrf_merge(
        rrf_inputs, max_results=candidate_limit,
    ), traces)
    rrf = [{**doc, "score": score} for doc, score in rrf_pairs]

    rerank_node = NodeRerank()
    state = {"rewritten_query": query, "rrf_chunks": rrf, "web_search_docs": []}
    if candidate_limit == retrieval_config.rerank_candidate_limit:
        pre_rerank = rerank_node._step_1_merge_multi_source_docs(state)
    else:
        # Evaluation-only candidate-budget ablation: keep the production
        # formatting but allow the explicitly requested wider RRF pool through.
        pre_rerank = [{
            "content": doc.get("content"), "title": doc.get("title"),
            "chunk_id": doc.get("chunk_id"), "url": None, "source": "local",
            "file_title": doc.get("file_title"),
        } for doc in rrf[:candidate_limit]]
    post_rerank = timed("rerank", lambda: rerank_node._step_2_rerank_merged_docs(state, pre_rerank), traces)
    post_rerank = post_rerank[:retrieval_config.final_output_limit]
    final_docs = timed("cutoff", lambda: rerank_node._step_3_cliff_cutoff(post_rerank), traces)
    for trace in traces:
        stage_docs = {
            "ordinary_hybrid": ordinary,
            "hyde_hybrid": hyde,
            "rrf": rrf,
            "rerank": post_rerank,
            "cutoff": final_docs,
        }.get(trace["stage"])
        trace["candidate_count"] = len(stage_docs) if stage_docs is not None else None
    traces.append({"stage": "total_retrieval", "latency_ms": round((time.perf_counter() - total_started) * 1000, 3), "error": None, "fallback": False, "candidate_count": len(final_docs)})
    return {
        "hyde_document": hyde_doc,
        "ordinary_retrieval": printable(ordinary),
        "hyde_retrieval": printable(hyde),
        "rrf_result": printable(rrf),
        "pre_rerank_result": printable(pre_rerank),
        "post_rerank_result": printable(post_rerank),
        "final_retrieval": printable(final_docs),
        "final_docs": final_docs,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DATASET)
    parser.add_argument("--collection", required=True, help="Isolated collection containing Evaluation V2 documents")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--allow-draft", action="store_true", help="Required until human review freezes the set")
    parser.add_argument("--candidate-limit", type=int, choices=(5, 10), default=5,
                        help="Evaluation-only targeted budget; production default remains 5")
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text(encoding="utf-8"))
    if dataset.get("status") != "FROZEN" and not args.allow_draft:
        raise SystemExit("Dataset is not FROZEN. Use --allow-draft only for review diagnostics, never final metrics.")
    run_id = f"evalv2-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    rows = []
    for case in dataset["cases"]:
        traces: list[dict[str, Any]] = []
        error = None
        stages = {}
        try:
            stages = retrieve(case["query"], args.collection, traces, args.candidate_limit)
            final_docs = stages.pop("final_docs")
        except Exception as exc:
            error = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
            final_docs = []
        row = {
            "run_id": run_id,
            "query_id": case["query_id"],
            "query": case["query"],
            "category": case["category"],
            "tags": case.get("tags", []),
            "answerable": case["answerable"],
            "relevant_documents": case["relevant_documents"],
            "relevant_locators": case["relevant_locators"],
            "metrics": metrics(final_docs, case["relevant_locators"]) if case["answerable"] else None,
            "no_answer_diagnostic": {
                "retrieval_has_candidate": bool(final_docs),
                "top_score": final_docs[0].get("score") if final_docs else None,
                "retrieved_documents": [doc.get("file_title") for doc in final_docs],
                "detection_status": "NO-ANSWER DETECTION NOT IMPLEMENTED",
            } if not case["answerable"] else None,
            "stages": stages,
            "trace": traces,
            "error": error,
        }
        rows.append(row)

    answerable_rows = [row for row in rows if row["answerable"] and row["metrics"]]
    aggregate = {
        metric: sum(float(row["metrics"][metric]) for row in answerable_rows) / len(answerable_rows)
        for metric in ("recall@1", "recall@3", "recall@5", "mrr@5")
    } if answerable_rows else {}
    by_category = {}
    for category in sorted({row["category"] for row in answerable_rows}):
        category_rows = [row for row in answerable_rows if row["category"] == category]
        by_category[category] = {
            "query_count": len(category_rows),
            **{
                metric: sum(float(row["metrics"][metric]) for row in category_rows) / len(category_rows)
                for metric in ("recall@1", "recall@3", "recall@5", "mrr@5")
            },
        }
    def percentile(values: list[float], percentile_value: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        position = (len(ordered) - 1) * percentile_value
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        fraction = position - lower
        return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction, 3)

    latency_by_stage = {}
    all_stages = sorted({trace["stage"] for row in rows for trace in row["trace"] if trace.get("error") is None})
    for stage in all_stages:
        values = [float(trace["latency_ms"]) for row in rows for trace in row["trace"] if trace["stage"] == stage and trace.get("error") is None]
        latency_by_stage[stage] = {"count": len(values), "p50_ms": percentile(values, 0.50), "p95_ms": percentile(values, 0.95), "mean_ms": round(sum(values) / len(values), 3) if values else None}

    from config.retrieval_config import retrieval_config
    from config.reranker_config import reranker_config
    manifest_path = MANIFEST_FROZEN if dataset.get("status") == "FROZEN" else MANIFEST_DRAFT
    artifact = {
        "run_id": run_id,
        "benchmark_status": "FINAL" if dataset.get("status") == "FROZEN" else "DRAFT_DIAGNOSTIC_ONLY",
        "dataset_status": dataset.get("status"),
        "dataset_manifest": json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None,
        "collection": args.collection,
        "retrieval_configuration": {
            "statement": "CURRENT PRODUCTION CONFIGURATION; NO TUNING BY EVALUATION V2",
            "ordinary_dense_sparse_weights": [0.8, 0.2],
            "hyde_dense_sparse_weights": [0.5, 0.5],
            "initial_candidate_limit": args.candidate_limit,
            "rrf_candidate_limit": args.candidate_limit,
            "rrf_k": 60,
            "rerank_candidate_limit": retrieval_config.rerank_candidate_limit,
            "final_output_limit": retrieval_config.final_output_limit,
            "evaluation_only_candidate_budget": args.candidate_limit,
            "rerank_model": reranker_config.text_rerank_model,
            "hyde_prompt_sha256": hashlib.sha256(__import__("processor.query_processor.prompt.search_embedding_hyde", fromlist=["HYDE_PROMPT"]).HYDE_PROMPT.encode()).hexdigest(),
            "query_rewrite": "disabled: independent single-turn evaluation queries",
            "parent_context": "enabled in frozen collection ingestion through current build_embedding_text",
            "cutoff": "current NodeRerank._step_3_cliff_cutoff",
        },
        "no_answer_detection": "NOT IMPLEMENTED",
        "aggregate_answerable_retrieval_metrics": aggregate,
        "metrics_by_category": by_category,
        "latency_summary": latency_by_stage,
        "queries": rows,
    }
    output = args.output or EVAL_ROOT / "artifacts" / f"{run_id}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": aggregate}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
