"""Locked, simple Evidence Gate for RAG Evaluation V2."""
from __future__ import annotations
from dataclasses import dataclass

class EmbeddingUnavailable(RuntimeError): pass
class VectorDatabaseUnavailable(RuntimeError): pass
class RetrievalFailed(RuntimeError): pass
class EvidenceInsufficient(RuntimeError): pass

@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    status: str
    top_score: float | None
    threshold: float
    answer: str | None

THRESHOLD = 0.75
RULE_VERSION = "calibration-v1-top1-hybrid-score"

def evaluate(candidates: list[dict]) -> GateDecision:
    if candidates is None:
        raise RetrievalFailed("retrieval error sentinel must not be treated as NO_RESULT")
    score = float(candidates[0]["score"]) if candidates else None
    accepted = score is not None and score >= THRESHOLD
    return GateDecision(accepted, "SUFFICIENT_EVIDENCE" if accepted else "NO_SUFFICIENT_EVIDENCE", score, THRESHOLD, None if accepted else "当前知识库中没有足够证据支持该问题。")
