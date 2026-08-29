"""Validate Evaluation V2 without importing any production retrieval component."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "dataset" / "dataset_v2_draft.json"
DEFAULT_REPORT = ROOT / "reports" / "validation_report.json"
LOCATOR_RE = re.compile(r"<!-- locator: ([A-Z0-9-]+) -->\n(.*?)(?=\n#{1,6} |\Z)", re.S)
CONTEXT_MARKER = "<!-- synthetic-section-context -->"
META_RE = re.compile(r"^---\n(.*?)\n---", re.S | re.M)
EXPECTED_CATEGORIES = {
    "exact_fact", "paraphrase_colloquial", "parent_context",
    "version_confusion", "multi_document", "table", "no_answer",
}
ALLOWED_TAGS = {
    "version_confusion", "parent_context", "table", "multi_document",
    "paraphrase", "no_answer", "similar_document",
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def shingles(text: str, width: int = 3) -> set[str]:
    value = normalize(text)
    return {value[i:i + width] for i in range(max(0, len(value) - width + 1))}


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


def lexical_overlap(query: str, evidence: str) -> dict[str, float]:
    q_chars = {c for c in normalize(query) if "\u4e00" <= c <= "\u9fff" or c.isalnum()}
    e_chars = {c for c in normalize(evidence) if "\u4e00" <= c <= "\u9fff" or c.isalnum()}
    q_tri = shingles(query)
    e_tri = shingles(evidence)
    return {
        "character_set_recall": round(len(q_chars & e_chars) / len(q_chars), 4) if q_chars else 0.0,
        "trigram_jaccard": round(jaccard(q_tri, e_tri), 4),
    }


def load_documents() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, str]], list[str]]:
    documents: dict[str, dict[str, Any]] = {}
    locators: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    for path in sorted((ROOT / "documents").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "SYNTHETIC / FOR EVALUATION ONLY" not in text:
            errors.append(f"missing synthetic notice: {path.name}")
        meta_match = META_RE.search(text)
        if not meta_match:
            errors.append(f"missing front matter: {path.name}")
            continue
        metadata = {}
        for line in meta_match.group(1).splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip().strip('"')
        document_id = metadata.get("document_id", "")
        required = ("document_id", "title", "version", "document_type", "synthetic")
        for key in required:
            if not metadata.get(key):
                errors.append(f"{path.name}: missing metadata {key}")
        if document_id in documents:
            errors.append(f"duplicate document_id: {document_id}")
        documents[document_id] = {"path": path, "metadata": metadata, "text": text}
        for locator, block in LOCATOR_RE.findall(text):
            if locator in locators:
                errors.append(f"duplicate locator: {locator}")
            locators[locator] = {
                "document_id": document_id,
                "text": " ".join(
                    line.strip()
                    for line in block.split(CONTEXT_MARKER, 1)[0].splitlines()
                    if line.strip()
                ),
            }
    return documents, locators, errors


def validate(dataset_path: Path) -> dict[str, Any]:
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    documents, locators, errors = load_documents()
    warnings: list[str] = []
    cases = dataset.get("cases", [])
    required_case_fields = {
        "query_id", "query", "category", "answerable", "relevant_documents",
        "relevant_locators", "reference_answer", "evidence", "notes", "difficulty",
        "requires_parent_context", "requires_multi_document", "expected_version",
        "review_status",
    }
    if dataset.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if dataset.get("synthetic") is not True:
        errors.append("dataset.synthetic must be true")
    if dataset.get("status") not in {"DRAFT", "READY_FOR_HUMAN_REVIEW", "FROZEN"}:
        errors.append("invalid dataset status")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty list")
    ids = [case.get("query_id") for case in cases]
    queries = [normalize(case.get("query", "")) for case in cases]
    if len(ids) != len(set(ids)):
        errors.append("query_id values are not unique")
    if len(queries) != len(set(queries)):
        errors.append("exact duplicate queries found")

    near_duplicates = []
    shingle_sets = [shingles(query) for query in queries]
    for left, right in combinations(range(len(cases)), 2):
        score = jaccard(shingle_sets[left], shingle_sets[right])
        if score >= 0.72:
            near_duplicates.append({
                "left": cases[left]["query_id"], "right": cases[right]["query_id"],
                "jaccard": round(score, 4),
            })

    category_counts = Counter(case.get("category") for case in cases)
    missing_categories = EXPECTED_CATEGORIES - set(category_counts)
    if missing_categories:
        errors.append(f"missing categories: {sorted(missing_categories)}")

    document_query_coverage = Counter()
    locator_query_coverage = Counter()
    overlaps = []
    for case in cases:
        qid = case.get("query_id", "<missing>")
        missing_fields = required_case_fields - set(case)
        if missing_fields:
            errors.append(f"{qid}: missing fields {sorted(missing_fields)}")
        if not re.fullmatch(r"v2q[0-9]{3}", str(qid)):
            errors.append(f"{qid}: invalid query_id format")
        if case.get("category") not in EXPECTED_CATEGORIES:
            errors.append(f"{qid}: invalid category")
        if case.get("difficulty") not in {"easy", "medium", "hard"}:
            errors.append(f"{qid}: invalid difficulty")
        if not isinstance(case.get("query"), str) or len(case.get("query", "").strip()) < 4:
            errors.append(f"{qid}: query is too short or invalid")
        answerable = case.get("answerable") is True
        case_docs = case.get("relevant_documents") or []
        case_locators = case.get("relevant_locators") or []
        evidence = case.get("evidence") or []
        if case.get("review_status") not in {"generated", "self_reviewed", "approved"}:
            errors.append(f"{qid}: invalid review_status")
        tags = case.get("tags", [])
        if not isinstance(tags, list) or len(tags) != len(set(tags)) or not set(tags) <= ALLOWED_TAGS:
            errors.append(f"{qid}: invalid or duplicate tags")
        if answerable and (not case_locators or not evidence or not case.get("reference_answer")):
            errors.append(f"{qid}: answerable case requires locators, evidence, reference answer")
        if not answerable and (case_docs or case_locators or evidence):
            errors.append(f"{qid}: no-answer case must not contain relevant documents/locators/evidence")
        if bool(case.get("requires_multi_document")) and len(case_docs) < 2:
            errors.append(f"{qid}: multi-document flag requires at least two documents")
        for document_id in case_docs:
            if document_id not in documents:
                errors.append(f"{qid}: unknown document {document_id}")
            document_query_coverage[document_id] += 1
        for index, locator in enumerate(case_locators):
            if locator not in locators:
                errors.append(f"{qid}: unknown locator {locator}")
                continue
            locator_query_coverage[locator] += 1
            source = locators[locator]
            if source["document_id"] not in case_docs:
                errors.append(f"{qid}: locator {locator} document missing from relevant_documents")
            if index >= len(evidence) or normalize(evidence[index]) not in normalize(source["text"]):
                errors.append(f"{qid}: evidence does not match source locator {locator}")
        if answerable:
            joined_evidence = " ".join(evidence)
            overlaps.append({"query_id": qid, **lexical_overlap(case["query"], joined_evidence)})

    no_answer_count = sum(not case.get("answerable") for case in cases)
    no_answer_ratio = no_answer_count / len(cases) if cases else 0.0
    if not 0.15 <= no_answer_ratio <= 0.25:
        errors.append(f"no-answer ratio outside 15%-25%: {no_answer_ratio:.4f}")
    if len(cases) < 110 or len(cases) > 130:
        warnings.append(f"query count outside preferred 110-130 range: {len(cases)}")

    overlap_sorted = sorted(overlaps, key=lambda item: (item["trigram_jaccard"], item["character_set_recall"]), reverse=True)
    high_overlap = [item for item in overlap_sorted if item["trigram_jaccard"] >= 0.30]
    report = {
        "status": "PASS" if not errors else "FAIL",
        "dataset_status": dataset.get("status"),
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "query_count": len(cases),
        "answerable_count": len(cases) - no_answer_count,
        "no_answer_count": no_answer_count,
        "no_answer_ratio": round(no_answer_ratio, 4),
        "category_distribution": dict(sorted(category_counts.items())),
        "tag_distribution": dict(sorted(Counter(tag for case in cases for tag in case.get("tags", [])).items())),
        "document_count": len(documents),
        "locator_count": len(locators),
        "documents_with_query_coverage": len(document_query_coverage),
        "locators_with_query_coverage": len(locator_query_coverage),
        "document_coverage": dict(sorted(document_query_coverage.items())),
        "uncovered_documents": sorted(set(documents) - set(document_query_coverage)),
        "uncovered_locators": sorted(set(locators) - set(locator_query_coverage)),
        "locator_coverage_ratio": round(len(locator_query_coverage) / len(locators), 4) if locators else 0.0,
        "special_coverage": {
            "version_confusion": category_counts["version_confusion"],
            "parent_context": category_counts["parent_context"],
            "multi_document": category_counts["multi_document"],
            "table": category_counts["table"],
        },
        "near_duplicate_diagnostics": near_duplicates,
        "lexical_overlap": {
            "method": "Chinese/alphanumeric character-set recall plus normalized character-trigram Jaccard; diagnostic only",
            "high_overlap_diagnostic_count": len(high_overlap),
            "top_20": overlap_sorted[:20],
        },
        "errors": errors,
        "warnings": warnings,
        "leakage_audit": {
            "validator_imports_production_retrieval": False,
            "builder_imports_production_retrieval": False,
            "labels_resolved_from": "Markdown locator blocks",
            "retriever_output_used_for_labels": False,
        },
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    report = validate(args.dataset)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in (
        "status", "query_count", "answerable_count", "no_answer_count",
        "no_answer_ratio", "category_distribution", "document_count",
        "locator_count", "locator_coverage_ratio", "errors", "warnings",
    )}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
