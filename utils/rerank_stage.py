"""Optional reranking with bounded latency and candidate fallback."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from utils.reranker_http_utils import rerank_documents


@dataclass(frozen=True)
class RerankResult:
    documents: list[dict]
    used: bool
    latency_ms: float
    scores: list[float]
    fallback: bool


def optional_rerank(query: str, documents: list[dict], enabled: bool, top_n: int, timeout: float) -> RerankResult:
    if not enabled or not documents:
        return RerankResult(documents, False, 0.0, [], False)
    started, output = time.perf_counter(), queue.Queue()

    def invoke():
        try:
            output.put(("ok", rerank_documents(query, [doc.get("content", "") for doc in documents])))
        except Exception as exc:
            output.put(("error", exc))

    threading.Thread(target=invoke, daemon=True).start()
    try:
        kind, value = output.get(timeout=timeout)
        if kind == "error" or len(value) != len(documents):
            raise RuntimeError("invalid rerank response")
        scored = [{**doc, "score": float(score), "rerank_score": float(score)}
                  for doc, score in zip(documents, value)]
        scored.sort(key=lambda doc: doc["score"], reverse=True)
        return RerankResult(scored[:top_n], True, round((time.perf_counter()-started)*1000, 3),
                            [float(x) for x in value], False)
    except Exception:
        return RerankResult(documents, True, round((time.perf_counter()-started)*1000, 3), [], True)
