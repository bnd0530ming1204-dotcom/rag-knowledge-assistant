"""Create a stable, category-balanced human-review sample from the draft."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset" / "dataset_v2_draft.json"
OUTPUT = ROOT / "reports" / "human_review_sample.md"

# 25 cases covering every category and deliberately difficult diagnostics.
SELECTED = [
    "v2q001", "v2q005", "v2q010", "v2q018",             # exact
    "v2q029", "v2q030", "v2q033", "v2q039",             # paraphrase
    "v2q047", "v2q051", "v2q056",                        # parent
    "v2q059", "v2q062", "v2q065", "v2q070",             # version
    "v2q071", "v2q074", "v2q078",                        # multi
    "v2q081", "v2q083", "v2q086",                        # table
    "v2q089", "v2q094", "v2q103", "v2q109",             # negative
]

FLAGS = {
    "v2q001": "LEXICAL_LEAKAGE_CANDIDATE",
    "v2q005": "LEXICAL_LEAKAGE_CANDIDATE",
    "v2q030": "DIFFICULT / WRONG-SCOPE RISK",
    "v2q047": "PARENT_CONTEXT",
    "v2q051": "PARENT_CONTEXT / ERROR-CODE CONFUSION",
    "v2q059": "VERSION_CONFUSION",
    "v2q062": "VERSION_CONFUSION / SAME ERROR CODE",
    "v2q065": "VERSION_CONFUSION / THREE DOCUMENTS",
    "v2q070": "VERSION_CONFUSION / SAME ERROR CODE",
    "v2q071": "MULTI_DOCUMENT / TABLE",
    "v2q074": "MULTI_DOCUMENT",
    "v2q078": "MULTI_DOCUMENT / GOVERNANCE",
    "v2q081": "TABLE",
    "v2q083": "TABLE",
    "v2q086": "TABLE",
    "v2q089": "NO_ANSWER / NONEXISTENT MODEL",
    "v2q094": "NO_ANSWER / UNSUPPORTED ROOT CAUSE",
    "v2q103": "NO_ANSWER / MISSING DEADLINE",
    "v2q109": "NO_ANSWER / UNSUPPORTED PERFORMANCE NUMBER",
}


def main() -> None:
    dataset = json.loads(DATASET.read_text(encoding="utf-8"))
    by_id = {case["query_id"]: case for case in dataset["cases"]}
    lines = [
        "# Evaluation V2 — Human Review Sample",
        "",
        "> **SYNTHETIC / FOR EVALUATION ONLY**",
        "",
        "> Status: `READY_FOR_HUMAN_REVIEW`. Reviewing this file does not freeze the dataset.",
        "",
        "Check whether each question is natural, answerability is correct, every source supports the reference answer, and the test value is genuine rather than benchmark decoration.",
        "",
    ]
    for index, query_id in enumerate(SELECTED, 1):
        case = by_id[query_id]
        lines.extend([
            f"## {index}. {query_id}",
            "",
            f"- **Query:** {case['query']}",
            f"- **Category:** `{case['category']}`",
            f"- **Answerable:** `{str(case['answerable']).lower()}`",
            f"- **Ground Truth Document:** {', '.join(case['relevant_documents']) or 'NONE'}",
            f"- **Ground Truth Locator:** {', '.join(case['relevant_locators']) or 'NONE'}",
            f"- **Ground Truth Evidence:** {' | '.join(case['evidence']) or 'NONE — negative query'}",
            f"- **Reference Answer:** {case['reference_answer']}",
            f"- **Why valuable:** {case['notes']}",
            f"- **Special flag:** `{FLAGS.get(query_id, 'GENERAL_REPRESENTATIVE')}`",
            "- **Human decision:** [ ] accept  [ ] revise  [ ] reject",
            "- **Reviewer note:**",
            "",
        ])
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(SELECTED)} review cases to {OUTPUT}")


if __name__ == "__main__":
    main()

