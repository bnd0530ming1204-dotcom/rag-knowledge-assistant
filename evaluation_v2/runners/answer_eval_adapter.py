"""Answer-level evaluation interface; no judge implementation is enabled yet."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AnswerEvaluationInput:
    query_id: str
    query: str
    answer: str
    retrieved_contexts: list[str]
    reference_answer: str


class AnswerEvaluator(Protocol):
    def evaluate(self, item: AnswerEvaluationInput) -> dict[str, float | str]: ...


STATUS = {
    "implementation": "INTERFACE_ONLY",
    "ragas": "NOT_CONFIGURED",
    "deterministic_metrics": ["recall@1", "recall@3", "recall@5", "mrr@5"],
    "llm_judge_metrics": ["faithfulness", "answer_relevancy", "context_precision", "context_recall"],
    "warning": "LLM-as-a-judge metrics are not answer accuracy and must be reported separately.",
}

