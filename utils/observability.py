"""Sanitized per-request traces for operations and evaluation analysis."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger("rag.request_trace")
_lock = threading.Lock()
_traces: dict[str, "RequestTrace"] = {}


@dataclass
class RequestTrace:
    request_id: str
    session_id: str
    original_query: str
    started_at: float = field(default_factory=time.perf_counter, repr=False)
    history_count: int = 0
    rewrite_required: bool = False
    rewrite_decision: str = "NO_REWRITE"
    rewrite_reason: str = ""
    rewrite_success: bool = False
    rewrite_query: str = ""
    rewrite_fallback: bool = False
    rewrite_latency_ms: float = 0.0
    retrieval_strategy: str = "weighted_hybrid"
    hyde_used: bool = False
    hyde_latency_ms: float = 0.0
    hyde_fallback: bool = False
    fusion_mode: str = "weighted_hybrid"
    dense_count: int = 0
    sparse_count: int = 0
    rrf_candidate_count: int = 0
    dense_weight: float = 0.8
    sparse_weight: float = 0.2
    candidate_count: int = 0
    rerank_used: bool = False
    rerank_latency_ms: float = 0.0
    rerank_scores: list[float] = field(default_factory=list)
    rerank_fallback: bool = False
    context_selector_mode: str = "fixed"
    selected_context_count: int = 0
    context_token_count: int = 0
    context_token_count_method: str = "approximate_cjk_plus_wordpiece"
    selection_reason: str = "fixed_rank_order"
    embedding_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    fallbacks: list[str] = field(default_factory=list)
    error_type: str | None = None
    terminal_status: str = "PROCESSING"

    def public_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("started_at", None)
        return value


def create_trace(request_id: str, session_id: str, query: str, dense_weight: float, sparse_weight: float) -> RequestTrace:
    trace = RequestTrace(request_id, session_id, query, dense_weight=dense_weight, sparse_weight=sparse_weight)
    with _lock:
        _traces[request_id] = trace
    return trace


def get_trace(request_id: str) -> RequestTrace | None:
    with _lock:
        return _traces.get(request_id)


def update_trace(request_id: str, **values: Any) -> None:
    trace = get_trace(request_id)
    if not trace:
        return
    for key, value in values.items():
        if hasattr(trace, key):
            setattr(trace, key, value)


def add_fallback(request_id: str, fallback: str) -> None:
    trace = get_trace(request_id)
    if trace and fallback not in trace.fallbacks:
        trace.fallbacks.append(fallback)


def finish_trace(request_id: str, status: str, error_type: str | None = None) -> None:
    trace = get_trace(request_id)
    if not trace:
        return
    trace.total_latency_ms = round((time.perf_counter() - trace.started_at) * 1000, 3)
    trace.terminal_status = status
    trace.error_type = error_type
    logger.info(json.dumps(trace.public_dict(), ensure_ascii=False, separators=(",", ":")))
