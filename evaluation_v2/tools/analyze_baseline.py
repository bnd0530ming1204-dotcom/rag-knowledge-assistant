"""Create evidence-based Evaluation V2 baseline failure reports.

This tool never changes the frozen corpus or ground truth. Automatic labels are
limited to directly observable rank/category conditions; uncertain root causes
remain explicitly marked for manual review.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def first_relevant(stage: list[dict[str, Any]], relevant: set[str]) -> int | None:
    return next((row["rank"] for row in stage if relevant.intersection(row.get("locators", []))), None)


def all_relevant(stage: list[dict[str, Any]], relevant: set[str]) -> bool:
    found = {locator for row in stage for locator in row.get("locators", [])}
    return relevant.issubset(found)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--frozen-manifest", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    manifest = json.loads(args.frozen_manifest.read_text(encoding="utf-8"))
    if baseline.get("dataset_status") != "FROZEN" or not str(manifest.get("status", "")).startswith("FROZEN"):
        raise SystemExit("Refusing analysis: baseline and manifest must both be FROZEN")

    # Correct the runner's embedded-manifest metadata bug without touching any
    # query trace or metric. Future runs select this manifest in the runner.
    baseline["dataset_manifest"] = manifest
    args.baseline.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    failures: list[dict[str, Any]] = []
    regressions: list[dict[str, Any]] = []
    hyde_review: list[dict[str, Any]] = []
    distribution: Counter[str] = Counter()
    no_answer_candidate_counts: Counter[int] = Counter()
    no_answer_top_documents: Counter[str] = Counter()
    no_answer_hyde_cases: list[dict[str, Any]] = []

    for query in baseline["queries"]:
        if not query["answerable"]:
            final = query.get("stages", {}).get("final_retrieval", [])
            no_answer_candidate_counts[len(final)] += 1
            if final:
                no_answer_top_documents[final[0]["document_id"]] += 1
            stages = query.get("stages", {})
            ordinary = stages.get("ordinary_retrieval", [])
            hyde = stages.get("hyde_retrieval", [])
            rrf = stages.get("rrf_result", [])
            no_answer_hyde_cases.append({
                "query_id": query["query_id"], "query": query["query"],
                "hyde_text": stages.get("hyde_document", ""),
                "ordinary_top_document": ordinary[0]["document_id"] if ordinary else None,
                "hyde_top_document": hyde[0]["document_id"] if hyde else None,
                "rrf_top_document": rrf[0]["document_id"] if rrf else None,
                "final_top_document": final[0]["document_id"] if final else None,
                "assessment": "HyDE supplied an assertive answer for a corpus-wide reviewed no-answer query; the assertion is unsupported by the frozen corpus. Retrieval causality is not asserted because no relevant rank exists.",
            })
            continue
        if query.get("error"):
            continue
        relevant = set(query["relevant_locators"])
        stages = query["stages"]
        ordinary_rank = first_relevant(stages["ordinary_retrieval"], relevant)
        hyde_rank = first_relevant(stages["hyde_retrieval"], relevant)
        rrf_rank = first_relevant(stages["rrf_result"], relevant)
        pre_rank = first_relevant(stages["pre_rerank_result"], relevant)
        post_rank = first_relevant(stages["post_rerank_result"], relevant)
        final_rank = first_relevant(stages["final_retrieval"], relevant)

        labels: list[str] = []
        if query["category"] == "multi_document" and not all_relevant(stages["final_retrieval"], relevant):
            labels.append("multi_document_incomplete")
        if query["category"] == "table" and query["metrics"]["recall@5"] < 1:
            labels.append("table_failure")
        if query["category"] == "version_confusion" and query["metrics"]["recall@1"] < 1:
            labels.append("wrong_version_or_rank_confusion")
        if query["category"] == "parent_context" and query["metrics"]["recall@5"] < 1:
            labels.append("parent_context_case_failed")
        if pre_rank is not None and (post_rank is None or post_rank > pre_rank):
            labels.append("rerank_regression")
            regressions.append({
                "query_id": query["query_id"], "query": query["query"],
                "pre_rerank_relevant_rank": pre_rank, "post_rerank_relevant_rank": post_rank,
                "final_relevant_rank": final_rank, "relevant_locators": sorted(relevant),
            })
        if ordinary_rank is not None and (rrf_rank is None or rrf_rank > ordinary_rank):
            hyde_review.append({
                "query_id": query["query_id"], "query": query["query"],
                "ordinary_relevant_rank": ordinary_rank, "hyde_relevant_rank": hyde_rank,
                "rrf_relevant_rank": rrf_rank, "final_relevant_rank": final_rank,
                "hyde_text": stages["hyde_document"],
                "assessment": "rank degradation after branch fusion; needs manual review before attributing causality to HyDE",
            })
        if query["metrics"]["recall@5"] < 1:
            if not labels:
                labels.append("unresolved_retrieval_failure")
            for label in labels:
                distribution[label] += 1
            failures.append({
                "query_id": query["query_id"], "query": query["query"],
                "category": query["category"], "tags": query["tags"],
                "recall@5": query["metrics"]["recall@5"], "mrr@5": query["metrics"]["mrr@5"],
                "relevant_locators": query["relevant_locators"],
                "final_top_documents": [row["document_id"] for row in stages["final_retrieval"]],
                "observed_labels": labels, "needs_manual_review": True,
            })

    failures.sort(key=lambda row: (row["recall@5"], row["mrr@5"], row["query_id"]))
    report = {
        "run_id": baseline["run_id"],
        "methodology": "rank/category evidence only; automatic labels are observations, not proven root causes",
        "answerable_failure_or_partial_count": len(failures),
        "top_failures": failures[:15],
        "hyde_rank_degradation_cases": hyde_review,
        "hyde_warning": "Generated text was not automatically judged factual; every case requires manual review.",
        "corpus_unsupported_no_answer_hyde_cases": no_answer_hyde_cases,
        "rerank_regression_cases": regressions,
        "observed_failure_distribution": dict(sorted(distribution.items())),
        "no_answer_observations": {
            "query_count": sum(no_answer_candidate_counts.values()),
            "returned_candidate_count_distribution": {str(k): v for k, v in sorted(no_answer_candidate_counts.items())},
            "top_document_distribution": dict(sorted(no_answer_top_documents.items())),
            "interpretation": "All are retrieval observations only; no-answer detection is not implemented and no accuracy is claimed.",
        },
    }
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Evaluation V2 Baseline Failure Report", "",
        f"Run: `{baseline['run_id']}`", "",
        "> Labels below are evidence-based observations, not automatically proven root causes. Uncertain cases require manual review.", "",
        f"Answerable failures or partial-recall cases: **{len(failures)}**", "", "## Top failures", "",
    ]
    for row in failures[:15]:
        lines += [f"- `{row['query_id']}` ({row['category']}): Recall@5={row['recall@5']:.4f}; labels={', '.join(row['observed_labels'])}; {row['query']}"]
    lines += ["", "## HyDE rank-degradation review candidates", ""]
    lines += [f"- `{row['query_id']}`: ordinary={row['ordinary_relevant_rank']}, HyDE={row['hyde_relevant_rank']}, RRF={row['rrf_relevant_rank']}, final={row['final_relevant_rank']}. Causality not asserted." for row in hyde_review] or ["- None observed."]
    lines += ["", "## Rerank regressions", ""]
    lines += [f"- `{row['query_id']}`: pre={row['pre_rerank_relevant_rank']}, post={row['post_rerank_relevant_rank']}, final={row['final_relevant_rank']}." for row in regressions] or ["- None observed."]
    lines += ["", "## Observed distribution", ""]
    lines += [f"- {label}: {count}" for label, count in sorted(distribution.items())]
    lines += ["", "## No-answer observations", "",
              f"- Query count: {sum(no_answer_candidate_counts.values())}",
              f"- Returned candidate counts: {dict(sorted(no_answer_candidate_counts.items()))}",
              "- NO-ANSWER DETECTION NOT IMPLEMENTED; no accuracy is claimed."]
    lines += ["", "## Corpus-unsupported HyDE on no-answer queries", "",
              f"- Assertive HyDE answers observed: {len(no_answer_hyde_cases)} / {sum(no_answer_candidate_counts.values())} reviewed no-answer queries.",
              "- These generations are unsupported by the frozen corpus. No causal retrieval-rank claim is made because no relevant locator exists."]
    args.markdown_output.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
