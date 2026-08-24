"""Minimal, offline comparison of dense-only and the current retriever.

This module does not invoke the query LangGraph, write chat history, or generate an
answer. Ground truth must be manually annotated in dataset.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_FIELDS = ["chunk_id", "content", "title", "file_title"]
SUPPORTED_K = (1, 3, 5)


def load_and_validate_dataset(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        dataset = json.load(handle)

    if dataset.get("schema_version") != 1:
        raise ValueError("dataset.schema_version must be 1")
    if dataset.get("dataset_status") not in {"template", "annotated"}:
        raise ValueError("dataset_status must be 'template' or 'annotated'")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("dataset.cases must be a non-empty list")

    seen_ids: set[str] = set()
    for index, case in enumerate(cases):
        prefix = f"cases[{index}]"
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            raise ValueError(f"{prefix}.id must be a non-empty string")
        if case_id in seen_ids:
            raise ValueError(f"duplicate case id: {case_id}")
        seen_ids.add(case_id)
        if not isinstance(case.get("query"), str) or not case["query"].strip():
            raise ValueError(f"{prefix}.query must be a non-empty string")
        relevant = case.get("relevant_chunks")
        if not isinstance(relevant, list) or not relevant:
            raise ValueError(f"{prefix}.relevant_chunks must be a non-empty list")
        for rel_index, locator in enumerate(relevant):
            locator_prefix = f"{prefix}.relevant_chunks[{rel_index}]"
            for required in ("file_title", "content_contains"):
                value = locator.get(required)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{locator_prefix}.{required} must be non-empty")
            title = locator.get("title")
            if title is not None and (not isinstance(title, str) or not title.strip()):
                raise ValueError(f"{locator_prefix}.title must be non-empty when present")
    return dataset


def normalize_hit(hit: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Milvus hit while retaining its retrieval score."""
    entity = hit.get("entity") or {}
    return {
        "chunk_id": str(entity.get("chunk_id", hit.get("id", ""))),
        "file_title": entity.get("file_title") or "",
        "title": entity.get("title") or "",
        "content": entity.get("content") or "",
        "score": float(hit.get("distance", hit.get("score")))
        if hit.get("distance", hit.get("score")) is not None
        else None,
    }


def dense_only(query: str, limit: int, collection_name: str) -> list[dict[str, Any]]:
    # Delayed imports keep --validate-only usable before runtime dependencies are installed.
    from config.milvus_config import milvus_config
    from utils.embedding_utils import generate_embeddings
    from utils.milvus_utils import get_milvus_client

    dense_vector = generate_embeddings([query])["dense"][0]
    response = get_milvus_client().search(
        collection_name=collection_name,
        data=[dense_vector],
        anns_field="dense_vector",
        search_params={"metric_type": "COSINE"},
        limit=limit,
        output_fields=OUTPUT_FIELDS,
    )
    return [normalize_hit(hit) for hit in (response[0] if response else [])]


def current_retrieval(
    query: str,
    limit: int,
    collection_name: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Reuse current hybrid, HyDE, RRF and rerank behavior without the chat graph.

    Metric ranking is captured before the production cliff cutoff so Recall@K has
    a fixed candidate budget. Cutoff output is retained as a diagnostic.
    """
    from config.milvus_config import milvus_config
    from config.retrieval_config import retrieval_config
    from processor.query_processor.nodes.c_node_search_embedding_hyde import NodeSearchEmbeddingHyde
    from processor.query_processor.nodes.e_node_rrf import NodeRrf
    from processor.query_processor.nodes.f_node_rerank import NodeRerank
    from utils.embedding_utils import generate_embeddings
    from utils.milvus_utils import create_hybrid_search_requests, get_milvus_client, hybrid_search

    embeddings = generate_embeddings([query])
    requests = create_hybrid_search_requests(
        embeddings["dense"][0],
        embeddings["sparse"][0],
        expr=None,
        limit=retrieval_config.initial_candidate_limit,
    )
    ordinary_response = hybrid_search(
        client=get_milvus_client(),
        collection_name=collection_name,
        reqs=requests,
        ranker_weights=(0.8, 0.2),
        limit=retrieval_config.initial_candidate_limit,
        output_fields=OUTPUT_FIELDS,
    )
    ordinary_hits = ordinary_response[0] if ordinary_response else []

    hyde_node = NodeSearchEmbeddingHyde()
    hyde_doc = hyde_node._step_1_create_embedding_hyde_doc(query)
    hyde_response = hyde_node._setp_2_search_embedding_hyde(
        query, hyde_doc, [], collection_name=collection_name
    )
    hyde_hits = hyde_response[0] if hyde_response else []

    rrf_inputs = [
        ([hit.get("entity") for hit in ordinary_hits if hit.get("entity")], 1.0),
        ([hit.get("entity") for hit in hyde_hits if hit.get("entity")], 1.0),
    ]
    rrf_docs = [
        doc
        for doc, _ in NodeRrf()._rrf_merge(
            rrf_inputs,
            max_results=retrieval_config.rrf_candidate_limit,
        )
    ]

    rerank_node = NodeRerank()
    rerank_candidates = rrf_docs[:retrieval_config.rerank_candidate_limit]
    state = {"rewritten_query": query, "rrf_chunks": rerank_candidates, "web_search_docs": []}
    merged = rerank_node._step_1_merge_multi_source_docs(state)
    reranked = rerank_node._step_2_rerank_merged_docs(state, merged) if merged else []
    final_ranked = reranked[:limit]
    cutoff = rerank_node._step_3_cliff_cutoff(final_ranked) if final_ranked else []

    ranked = [{**doc, "chunk_id": str(doc.get("chunk_id", ""))} for doc in final_ranked]
    diagnostics = {
        "hyde_doc": hyde_doc,
        "collection_name": collection_name,
        "candidate_counts": {
            "ordinary_hybrid": len(ordinary_hits),
            "hyde_hybrid": len(hyde_hits),
            "rrf": len(rrf_docs),
            "rerank_input": len(rerank_candidates),
            "after_actual_cutoff": len(cutoff),
        },
        "actual_cutoff_chunk_ids": [str(doc.get("chunk_id", "")) for doc in cutoff],
    }
    return ranked, diagnostics


def locator_matches(doc: dict[str, Any], locator: dict[str, str]) -> bool:
    if str(doc.get("file_title", "")) != locator["file_title"]:
        return False
    if "title" in locator and str(doc.get("title", "")) != locator["title"]:
        return False
    # inspect_chunks displays normalized whitespace; normalize both sides so a
    # copied label remains valid when the source contains newlines/tabs.
    normalized_content = " ".join(str(doc.get("content", "")).split())
    normalized_needle = " ".join(locator["content_contains"].split())
    return normalized_needle in normalized_content


def score_case(ranked: list[dict[str, Any]], ground_truth: list[dict[str, str]]) -> dict[str, Any]:
    """Recall@K counts distinct relevant locators found; MRR uses first relevant hit."""
    matched_locator_indices_by_rank: list[list[int]] = []
    for doc in ranked:
        matched_locator_indices_by_rank.append(
            [index for index, locator in enumerate(ground_truth) if locator_matches(doc, locator)]
        )

    recalls: dict[str, float] = {}
    hits: dict[str, bool] = {}
    for k in SUPPORTED_K:
        found = {
            locator_index
            for indices in matched_locator_indices_by_rank[:k]
            for locator_index in indices
        }
        recalls[f"recall@{k}"] = len(found) / len(ground_truth)
        hits[f"hit@{k}"] = bool(found)

    first_rank = next(
        (rank for rank, indices in enumerate(matched_locator_indices_by_rank[:5], start=1) if indices),
        None,
    )
    return {
        **recalls,
        **hits,
        "mrr@5": 1.0 / first_rank if first_rank is not None else 0.0,
        "first_relevant_rank": first_rank,
        "matched_ground_truth_indices": sorted(
            {index for indices in matched_locator_indices_by_rank[:5] for index in indices}
        ),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    metric_names = ("recall@1", "recall@3", "recall@5", "mrr@5")
    return {
        metric: sum(row["metrics"][metric] for row in rows) / len(rows)
        for metric in metric_names
    }


def printable_doc(doc: dict[str, Any]) -> dict[str, Any]:
    raw_score = doc.get("score")
    return {
        "rank": doc["rank"],
        "chunk_id": doc.get("chunk_id"),
        "file_title": doc.get("file_title"),
        "title": doc.get("title"),
        "score": float(raw_score) if raw_score is not None else None,
        "content_preview": str(doc.get("content", ""))[:300],
    }


def evaluate(
    dataset: dict[str, Any],
    dense_collection: str,
    current_collection: str,
) -> dict[str, Any]:
    per_mode: dict[str, list[dict[str, Any]]] = {"dense_only": [], "current": []}
    for case in dataset["cases"]:
        query = case["query"]
        ground_truth = case["relevant_chunks"]
        dense_docs = dense_only(query, limit=5, collection_name=dense_collection)
        current_docs, diagnostics = current_retrieval(
            query, limit=5, collection_name=current_collection
        )
        for mode, docs, extra in (
            ("dense_only", dense_docs, {}),
            ("current", current_docs, {"diagnostics": diagnostics}),
        ):
            ranked = [{**doc, "rank": rank} for rank, doc in enumerate(docs, start=1)]
            per_mode[mode].append(
                {
                    "id": case["id"],
                    "query": query,
                    "ground_truth": ground_truth,
                    "metrics": score_case(ranked, ground_truth),
                    "top_k": [printable_doc(doc) for doc in ranked],
                    **extra,
                }
            )
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_size": len(dataset["cases"]),
        "dataset_description": dataset.get("description", ""),
        "collections": {
            "dense_only": dense_collection,
            "current": current_collection,
        },
        "comparison_notes": {
            "query_rewrite": "disabled for both modes",
            "current_metric_stage": "after rerank ordering, before dynamic cliff cutoff",
            "ground_truth": "manually annotated stable locators; no generated labels",
        },
        "modes": {
            mode: {"metrics": aggregate(rows), "queries": rows}
            for mode, rows in per_mode.items()
        },
    }


def print_summary(results: dict[str, Any]) -> None:
    for label, key in (("Dense Only", "dense_only"), ("Current Retrieval", "current")):
        metrics = results["modes"][key]["metrics"]
        print(f"\n{label}")
        for metric in ("recall@1", "recall@3", "recall@5", "mrr@5"):
            print(f"{metric.replace('recall', 'Recall').replace('mrr', 'MRR')}: {metrics[metric]:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("dataset.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "results" / "latest.json")
    parser.add_argument("--dense-collection")
    parser.add_argument("--current-collection")
    parser.add_argument("--validate-only", action="store_true", help="Validate format without retrieval")
    args = parser.parse_args()

    dataset = load_and_validate_dataset(args.dataset)
    print(f"Dataset format valid: {len(dataset['cases'])} cases, status={dataset['dataset_status']}")
    if args.validate_only:
        return
    if dataset["dataset_status"] != "annotated":
        raise SystemExit(
            "Refusing to evaluate template data. Replace examples with manual labels and set "
            "dataset_status to 'annotated'."
        )

    from config.milvus_config import milvus_config

    dense_collection = args.dense_collection or milvus_config.chunks_collection
    current_collection = args.current_collection or milvus_config.chunks_collection
    results = evaluate(dataset, dense_collection, current_collection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)
    print_summary(results)
    print(f"\nMachine-readable result: {args.output.resolve()}")


if __name__ == "__main__":
    main()
