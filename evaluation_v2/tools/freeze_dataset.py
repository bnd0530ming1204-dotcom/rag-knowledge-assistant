"""Freeze an approved Evaluation V2 draft. Do not run before human approval."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation_v2.validators.validate_dataset import validate

DRAFT = ROOT / "dataset" / "dataset_v2_draft.json"
FROZEN = ROOT / "dataset" / "dataset_v2_frozen.json"
FROZEN_MANIFEST = ROOT / "artifacts" / "manifest_frozen.json"
FROZEN_DOCS = ROOT / "documents_frozen"
LOCATOR_RE = re.compile(r"<!-- locator: ([A-Z0-9-]+) -->")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approval-token", required=True)
    args = parser.parse_args()
    if args.approval_token != "HUMAN_REVIEW_APPROVED":
        raise SystemExit("Refusing to freeze without the exact human approval token.")
    report = validate(DRAFT)
    if report["status"] != "PASS":
        raise SystemExit(f"Refusing to freeze invalid dataset: {report['errors']}")
    dataset = json.loads(DRAFT.read_text(encoding="utf-8"))
    dataset["status"] = "FROZEN"
    dataset["frozen_at"] = datetime.now(timezone.utc).isoformat()
    payload = (json.dumps(dataset, ensure_ascii=False, indent=2) + "\n").encode()
    if FROZEN.exists() or FROZEN_DOCS.exists() or FROZEN_MANIFEST.exists():
        raise SystemExit("Frozen artifacts already exist; use correction log and a new version.")
    FROZEN_DOCS.mkdir(parents=True)
    documents = []
    locator_count = 0
    for source in sorted((ROOT / "documents").glob("*.md")):
        target = FROZEN_DOCS / source.name
        shutil.copyfile(source, target)
        payload_doc = target.read_bytes()
        text = payload_doc.decode("utf-8")
        locator_count += len(LOCATOR_RE.findall(text))
        document_id_match = re.search(r"^document_id:\s*(.+)$", text, re.M)
        documents.append({
            "document_id": document_id_match.group(1).strip() if document_id_match else source.stem.upper(),
            "file": f"documents_frozen/{source.name}",
            "sha256": hashlib.sha256(payload_doc).hexdigest(),
        })
    FROZEN.write_bytes(payload)
    corpus_hash_input = "".join(
        f"{item['document_id']}:{item['sha256']}\n" for item in sorted(documents, key=lambda x: x["document_id"])
    ).encode()
    manifest = {
        "status": "FROZEN EVALUATION SET",
        "dataset_path": "dataset/dataset_v2_frozen.json",
        "dataset_sha256": hashlib.sha256(payload).hexdigest(),
        "corpus_manifest_sha256": hashlib.sha256(corpus_hash_input).hexdigest(),
        "query_count": len(dataset["cases"]),
        "document_count": len(documents),
        "locator_count": locator_count,
        "category_distribution": dict(sorted(Counter(case["category"] for case in dataset["cases"]).items())),
        "tag_distribution": dict(sorted(Counter(tag for case in dataset["cases"] for tag in case.get("tags", [])).items())),
        "answerable_count": sum(case["answerable"] for case in dataset["cases"]),
        "no_answer_count": sum(not case["answerable"] for case in dataset["cases"]),
        "frozen_at": dataset["frozen_at"],
        "documents": documents,
        "correction_policy": "Corrections require correction_log.jsonl and a new dataset version; never edit silently.",
    }
    FROZEN_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("FROZEN EVALUATION SET created after explicit approval")


if __name__ == "__main__":
    main()
