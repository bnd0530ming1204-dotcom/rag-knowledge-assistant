"""Candidate fusion primitives. Explicit RRF fuses dense and sparse rank lists."""
from __future__ import annotations

from typing import Any

from utils.metadata_utils import normalize_chunk_metadata


def _entity(hit: Any) -> dict:
    entity = hit.get("entity") if isinstance(hit, dict) else getattr(hit, "entity", None)
    value = normalize_chunk_metadata(dict(entity or {}))
    score = hit.get("distance") if isinstance(hit, dict) else getattr(hit, "distance", None)
    value["score"] = float(score) if score is not None else None
    value.setdefault("source", "local")
    value.setdefault("url", None)
    return value


def reciprocal_rank_fusion(dense_hits: list, sparse_hits: list, k: int = 60, top_n: int = 10) -> list[dict]:
    scores: dict[str, float] = {}
    documents: dict[str, dict] = {}
    for rank_list in (dense_hits or [], sparse_hits or []):
        for rank, hit in enumerate(rank_list, start=1):
            doc = _entity(hit)
            key = doc["chunk_id"] or f"{doc['document_id']}:{doc['title']}:{doc['content']}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            documents.setdefault(key, doc)
    ordered = sorted(scores, key=lambda key: scores[key], reverse=True)
    output = []
    for key in ordered[:top_n]:
        output.append({**documents[key], "score": scores[key], "fusion_score": scores[key]})
    return output
