"""Lightweight, explainable retrieval strategy routing."""
from __future__ import annotations

import re
from dataclasses import dataclass


NORMAL_HYBRID = "NORMAL_HYBRID"
HYDE_HYBRID = "HYDE_HYBRID"


@dataclass(frozen=True)
class StrategyDecision:
    strategy: str
    reason: str


_FACT_LIKE = re.compile(r"多少|多久|哪一|什么时间|版本|型号|步骤|端口|电压|带宽|保修|是否|能否")
_DESCRIPTIVE = re.compile(r"解释|概述|原理|为什么|如何理解|有什么影响|分析|介绍")


def route_strategy(query: str, enable_hyde: bool) -> StrategyDecision:
    if not enable_hyde:
        return StrategyDecision(NORMAL_HYBRID, "hyde_disabled")
    text = (query or "").strip()
    if _FACT_LIKE.search(text):
        return StrategyDecision(NORMAL_HYBRID, "fact_like_query")
    if _DESCRIPTIVE.search(text) or len(text) >= 40:
        return StrategyDecision(HYDE_HYBRID, "descriptive_semantic_query")
    return StrategyDecision(NORMAL_HYBRID, "default_normal")
