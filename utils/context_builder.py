"""Fixed-rank, token-aware context builder for production RAG."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from utils.metadata_utils import normalize_chunk_metadata


def estimate_tokens(text: str) -> int:
    """Conservative lightweight estimate; this is not an exact model tokenizer."""
    if not text:
        return 0
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    non_cjk = re.sub(r"[\u3400-\u9fff]", " ", text)
    words = len(re.findall(r"\w+|[^\w\s]", non_cjk, flags=re.UNICODE))
    return cjk + words


@dataclass(frozen=True)
class ContextBuildResult:
    text: str
    documents: list[dict[str, Any]]
    token_count: int
    token_count_method: str = "approximate_cjk_plus_wordpiece"
    selection_reason: str = "fixed_rank_order"


def build_fixed_context(
    documents: list[dict[str, Any]],
    max_tokens: int,
    max_contexts: int,
    min_contexts: int = 1,
    max_per_parent: int = 2,
) -> ContextBuildResult:
    selected, entries = [], []
    seen_ids, seen_content, parent_counts = set(), set(), {}
    used_tokens = 0

    for raw in documents or []:
        if len(selected) >= max_contexts:
            break
        doc = normalize_chunk_metadata(raw)
        content_key = " ".join(doc["content"].split())
        chunk_id = doc["chunk_id"]
        if not content_key or content_key in seen_content or (chunk_id and chunk_id in seen_ids):
            continue
        parent_key = (doc["document_id"], doc["parent_title"] or doc["section_title"])
        if parent_key[1] and parent_counts.get(parent_key, 0) >= max_per_parent:
            continue
        index = len(selected) + 1
        tags = [f"[{index}]", f"[chunk_id={chunk_id}]", f"[document={doc['document_name']}]",
                f"[title={doc['title']}]", f"[parent={doc['parent_title']}]" ]
        entry = " ".join(tag for tag in tags if not tag.endswith("=]")) + "\n" + doc["content"]
        entry_tokens = estimate_tokens(entry)
        if used_tokens + entry_tokens > max_tokens:
            if len(selected) >= min_contexts:
                continue
            # Preserve one useful context under an unusually small budget.
            allowed = max(1, max_tokens - estimate_tokens(" ".join(tags) + "\n"))
            doc["content"] = doc["content"][:allowed]
            entry = " ".join(tags) + "\n" + doc["content"]
            entry_tokens = estimate_tokens(entry)
        selected.append(doc)
        entries.append(entry)
        used_tokens += entry_tokens
        seen_content.add(content_key)
        if chunk_id:
            seen_ids.add(chunk_id)
        if parent_key[1]:
            parent_counts[parent_key] = parent_counts.get(parent_key, 0) + 1

    return ContextBuildResult("\n\n".join(entries), selected, used_tokens)


def select_context(
    documents: list[dict[str, Any]], mode: str, max_tokens: int,
    fixed_top_k: int, min_contexts: int, max_contexts: int,
    score_gap: float, min_score: float | None,
) -> ContextBuildResult:
    if mode == "fixed":
        return build_fixed_context(documents, max_tokens, fixed_top_k, min_contexts=min_contexts)

    chosen = []
    reason = "dynamic_max_contexts"
    for index, doc in enumerate(documents or []):
        score = doc.get("score")
        if index >= min_contexts:
            if min_score is not None and score is not None and float(score) < min_score:
                reason = "dynamic_min_score"
                break
            previous = documents[index - 1].get("score")
            if previous is not None and score is not None and float(previous) - float(score) >= score_gap:
                reason = "dynamic_score_gap"
                break
        chosen.append(doc)
        if len(chosen) >= max_contexts:
            break
    if len(chosen) < min_contexts:
        chosen = list((documents or [])[:min_contexts])
        reason = "dynamic_minimum_protection"
    result = build_fixed_context(chosen, max_tokens, max_contexts, min_contexts=min_contexts)
    return ContextBuildResult(result.text, result.documents, result.token_count,
                              result.token_count_method, reason)
