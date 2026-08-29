"""Verify isolated collection row count and update the ingestion artifact."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.milvus_utils import get_milvus_client


COLLECTION = "rag_eval_v2_chunks"
ARTIFACT = EVAL_ROOT / "artifacts" / "ingestion_frozen.json"


def main() -> None:
    client = get_milvus_client()
    if not client.has_collection(COLLECTION):
        raise SystemExit(f"missing collection: {COLLECTION}")
    client.flush(COLLECTION)
    row_count = 0
    for _ in range(20):
        stats = client.get_collection_stats(COLLECTION)
        row_count = int(stats.get("row_count", 0))
        if row_count:
            break
        time.sleep(0.5)
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    artifact["collection_row_count"] = row_count
    artifact["row_count_verified"] = row_count == artifact.get("insert_count") == artifact.get("chunk_count")
    ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"collection": COLLECTION, "row_count": row_count, "verified": artifact["row_count_verified"]}, ensure_ascii=False))
    if not artifact["row_count_verified"]:
        raise SystemExit("collection row count verification failed")


if __name__ == "__main__":
    main()
