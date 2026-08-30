"""Deterministic generation metrics. These are rule scores, not human accuracy."""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict


def _units(text: str) -> set[str]:
    value = re.sub(r"\s+", "", (text or "").lower())
    tokens = set(re.findall(r"[a-z]+|\d+(?:\.\d+)?|[\u3400-\u9fff]{1,4}", value))
    tokens.update(value[i:i+2] for i in range(max(0, len(value)-1)))
    return {x for x in tokens if x}


def _coverage(target: str, candidate: str) -> float:
    expected = _units(target)
    return 1.0 if not expected else len(expected & _units(candidate)) / len(expected)


def split_required_facts(reference_answer: str, required_facts: list[str] | None = None) -> list[str]:
    if required_facts:
        return [fact.strip() for fact in required_facts if fact.strip()]
    return [part.strip() for part in re.split(r"[。；;]", reference_answer or "") if part.strip()]


def answer_correctness(answer: str, required_facts: list[str]) -> float:
    if not required_facts:
        return 0.0
    return sum(_coverage(fact, answer) >= 0.6 for fact in required_facts) / len(required_facts)


def faithfulness(answer: str, selected_contexts: list[dict]) -> float:
    claims = [x.strip() for x in re.split(r"[。！？!?；;]", answer or "") if len(x.strip()) >= 3]
    if not claims:
        return 1.0
    evidence = "\n".join(str(doc.get("content") or "") for doc in selected_contexts)
    return sum(_coverage(claim, evidence) >= 0.5 for claim in claims) / len(claims)


def citation_correctness(citations: list[dict], selected_contexts: list[dict], required_locators: list[str]) -> float:
    selected_ids = {str(doc.get("chunk_id") or "") for doc in selected_contexts}
    selected_locators = {x for doc in selected_contexts for x in _doc_locators(doc)}
    valid = all(str(cite.get("chunk_id") or "") in selected_ids for cite in citations) if citations else False
    locator_covered = not required_locators or bool(set(required_locators) & selected_locators)
    no_fake_page = all("page" not in cite or cite.get("page") is not None for cite in citations)
    return float(valid and locator_covered and no_fake_page)


def context_relevance(selected_contexts: list[dict], relevant_locators: list[str]) -> float:
    if not selected_contexts:
        return 0.0
    relevant = set(relevant_locators)
    return sum(bool(relevant & _doc_locators(doc)) for doc in selected_contexts) / len(selected_contexts)


_REFUSAL = re.compile(r"没有足够|无法根据|知识库中未|未找到|不能确定|无法确定|无法确认|未提及")
_FACTUAL = re.compile(r"\d|是|为|支持|需要|可以|保修|必须|建议")


def no_answer_behavior(answer: str, answerable: bool) -> str:
    if answerable:
        return "NOT_APPLICABLE"
    if _REFUSAL.search(answer or ""):
        return "SUPPORTED_REFUSAL"
    if _FACTUAL.search(answer or ""):
        return "UNSUPPORTED_FACTUAL_CLAIM"
    return "UNCERTAIN_NEEDS_REVIEW"


def evaluate_generation(item: dict) -> dict:
    facts = split_required_facts(item.get("reference_answer", ""), item.get("required_facts"))
    contexts = item.get("selected_contexts") or []
    citations = item.get("citations") or []
    return {
        **item,
        "required_facts": facts,
        "answer_correctness": round(answer_correctness(item.get("answer", ""), facts), 4),
        "faithfulness": round(faithfulness(item.get("answer", ""), contexts), 4),
        "citation_correctness": citation_correctness(citations, contexts, item.get("relevant_locators") or []),
        "context_relevance": round(context_relevance(contexts, item.get("relevant_locators") or []), 4),
        "no_answer_behavior": no_answer_behavior(item.get("answer", ""), bool(item.get("answerable", True))),
        "metric_type": "DETERMINISTIC_RULE_BASED_NOT_HUMAN_ACCURACY"
    }
_LOCATOR = re.compile(r"<!--\s*locator:\s*([^>]+?)\s*-->", re.I)


def _doc_locators(doc: dict) -> set[str]:
    explicit = {str(x) for x in (doc.get("locators") or [])}
    parsed = {x.strip() for x in _LOCATOR.findall(str(doc.get("content") or ""))}
    return explicit | parsed
