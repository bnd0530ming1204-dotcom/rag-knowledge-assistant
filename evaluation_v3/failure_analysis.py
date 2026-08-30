"""Evidence-limited failure labels; root causes remain hypotheses."""
FAILURE_TYPES = {
    "REWRITE_DRIFT", "HISTORY_POLLUTION", "HYDE_DRIFT", "DENSE_MISS", "SPARSE_MISS",
    "FUSION_RANKING", "RERANK_DEGRADE", "CONTEXT_OVERSELECT", "CONTEXT_UNDERSELECT",
    "CONTEXT_DUPLICATION", "KNOWLEDGE_MISSING", "GENERATION_INCORRECT",
    "GENERATION_UNFAITHFUL", "CITATION_MISMATCH", "NO_ANSWER_FALSE_CLAIM",
    "INFRASTRUCTURE_FAILURE", "NEEDS_REVIEW",
}


def classify(row: dict) -> list[dict]:
    failures = []
    def add(kind, evidence, candidate_fix, regression=False):
        failures.append({"failure_type": kind, "evidence": evidence,
                         "root_cause": "HYPOTHESIS_REQUIRES_REVIEW",
                         "candidate_fix": candidate_fix, "whether_regression_case": regression})
    if row.get("error_type"):
        add("INFRASTRUCTURE_FAILURE", row["error_type"], "restore dependency and rerun", True)
    if row.get("rewrite_fallback") and row.get("rewrite_query") != row.get("original_query"):
        add("REWRITE_DRIFT", "rewrite changed despite fallback", "inspect rewrite contract", True)
    if row.get("answer_correctness", 1) < 1:
        add("GENERATION_INCORRECT", f"correctness={row.get('answer_correctness')}", "inspect missing facts", True)
    if row.get("faithfulness", 1) < 1:
        add("GENERATION_UNFAITHFUL", f"faithfulness={row.get('faithfulness')}", "inspect claims vs contexts", True)
    if row.get("citation_correctness", 1) < 1:
        add("CITATION_MISMATCH", "citation does not match selected context/locator", "bind citations to selected chunks", True)
    if row.get("no_answer_behavior") == "UNSUPPORTED_FACTUAL_CLAIM":
        add("NO_ANSWER_FALSE_CLAIM", "unsupported query produced factual assertion", "evaluate refusal policy", True)
    if not failures and any(row.get(key) is not None for key in ("answer_correctness", "faithfulness")):
        return []
    return failures or [{"failure_type":"NEEDS_REVIEW", "evidence":"insufficient automatic evidence",
                         "root_cause":"UNKNOWN", "candidate_fix":"manual review",
                         "whether_regression_case":False}]
