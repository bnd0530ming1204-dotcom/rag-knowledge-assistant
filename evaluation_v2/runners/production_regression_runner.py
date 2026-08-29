"""Run the frozen set through the actual production retrieval node.

This runner changes no retrieval behavior. It only redirects the production
node to the isolated Evaluation V2 Milvus collection and records its outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[2]
EVAL = ROOT / "evaluation_v2"
sys.path.insert(0, str(ROOT))

from config.milvus_config import milvus_config
from config.retrieval_config import retrieval_config
from evaluation_v2.runners.baseline_runner import metrics, printable
from processor.query_processor.nodes.b_node_search_embedding import NodeSearchEmbedding


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * p
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return round(ordered[lower] * (1 - fraction) + ordered[upper] * fraction, 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=EVAL / "dataset" / "dataset_v2_frozen.json",
    )
    args = parser.parse_args()

    raw_dataset = args.dataset.read_bytes()
    dataset = json.loads(raw_dataset)
    if dataset.get("status") != "FROZEN":
        raise SystemExit("Production regression requires the FROZEN dataset")
    manifest = json.loads((EVAL / "artifacts" / "manifest_frozen.json").read_text(encoding="utf-8"))

    # Evaluation isolation only: point the unmodified production node at the
    # dedicated frozen-corpus collection for this process.
    object.__setattr__(milvus_config, "chunks_collection", args.collection)
    node = NodeSearchEmbedding()
    rows = []
    latencies = []
    errors = []

    for case in dataset["cases"]:
        started = time.perf_counter()
        try:
            result = node.process({"rewritten_query": case["query"]})
            docs = result["reranked_docs"]
            error = None
        except Exception as exc:
            docs = []
            error = {"type": type(exc).__name__, "message": str(exc)}
            errors.append({"query_id": case["query_id"], **error})
        latency_ms = round((time.perf_counter() - started) * 1000, 3)
        latencies.append(latency_ms)
        rows.append({
            "query_id": case["query_id"],
            "query": case["query"],
            "category": case["category"],
            "tags": case.get("tags", []),
            "answerable": case["answerable"],
            "relevant_documents": case["relevant_documents"],
            "relevant_locators": case["relevant_locators"],
            "results": printable(docs),
            "metrics": metrics(docs, case["relevant_locators"]) if case["answerable"] else None,
            "latency_ms": latency_ms,
            "error": error,
        })

    answerable = [row for row in rows if row["answerable"] and row["metrics"]]
    metric_names = ("recall@1", "recall@3", "recall@5", "mrr@5")
    aggregate = {
        name: sum(float(row["metrics"][name]) for row in answerable) / len(answerable)
        for name in metric_names
    }
    by_category = {}
    for category in sorted({row["category"] for row in answerable}):
        category_rows = [row for row in answerable if row["category"] == category]
        by_category[category] = {
            "query_count": len(category_rows),
            **{
                name: sum(float(row["metrics"][name]) for row in category_rows) / len(category_rows)
                for name in metric_names
            },
        }

    artifact = {
        "run_id": f"production-regression-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}",
        "run_type": "FINAL_PRODUCTION_RETRIEVAL_REGRESSION",
        "dataset_status": dataset["status"],
        "dataset_sha256": hashlib.sha256(raw_dataset).hexdigest(),
        "corpus_manifest_sha256": manifest["corpus_manifest_sha256"],
        "git_commit_before_acceptance": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "collection": args.collection,
        "production_config": {
            "dense_weight": retrieval_config.dense_weight,
            "sparse_weight": retrieval_config.sparse_weight,
            "candidate_limit": retrieval_config.initial_candidate_limit,
            "final_top_k": retrieval_config.final_output_limit,
            "hyde": False,
            "rrf": False,
            "rerank": False,
            "cliff_cutoff": False,
        },
        "query_count": len(rows),
        "complete_latency_samples": len(latencies),
        "errors": errors,
        "metrics": aggregate,
        "metrics_by_category": by_category,
        "latency": {
            "count": len(latencies),
            "p50_ms": percentile(latencies, 0.50),
            "p95_ms": percentile(latencies, 0.95),
            "mean_ms": round(mean(latencies), 3),
        },
        "queries": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "query_count": len(rows),
        "errors": len(errors),
        "metrics": aggregate,
        "latency": artifact["latency"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
