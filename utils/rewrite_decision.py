"""Explainable query rewrite decision rules."""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class RewriteDecision:
    required: bool
    decision: str
    reason: str


_DEPENDENT = re.compile(
    r"(^|[，。？！?\s])(它|他|她|这个|那个|这款|该|其|上述|前者|后者|第二个|第一个|那|然后呢|还有呢)"
)
_ELLIPSIS = re.compile(r"^(那|那么|第二个|另一个|然后|还有|价格呢|多久呢|怎么呢).{0,12}[呢吗？?]?$" )


def decide_rewrite(query: str, history: list[dict], mode: str = "conditional") -> RewriteDecision:
    if not history:
        return RewriteDecision(False, "NO_REWRITE", "no_history")
    if mode == "history":
        return RewriteDecision(True, "REWRITE", "history_mode_compatibility")
    text = (query or "").strip()
    if _DEPENDENT.search(text):
        return RewriteDecision(True, "REWRITE", "coreference_marker")
    if _ELLIPSIS.search(text) or len(text) <= 6 and text.endswith(("呢", "？", "?")):
        return RewriteDecision(True, "REWRITE", "ellipsis_or_short_followup")
    return RewriteDecision(False, "NO_REWRITE", "standalone_query")
