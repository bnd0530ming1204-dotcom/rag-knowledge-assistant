"""Build a non-destructive Parent Context Embedding experiment collection."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pymilvus import DataType


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.milvus_config import milvus_config  # noqa: E402
from utils.embedding_utils import generate_embeddings  # noqa: E402
from utils.milvus_utils import escape_milvus_string, get_milvus_client  # noqa: E402


DEFAULT_FILE_TITLE = "澄云智控平台用户手册_RAG评测版"
DEFAULT_EXPERIMENT_COLLECTION = "kb_chunks_parent_context_v1"
NUMBERED_TITLE = re.compile(r"^\s*#{1,6}\s+(\d+(?:\.\d+)*)\s+(.+?)\s*$")


def infer_parent_context(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Infer the nearest prior numbered ancestor without using queries or labels."""
    titles_by_path: dict[tuple[str, ...], str] = {}
    augmented: list[dict[str, Any]] = []
    for source in sorted(rows, key=lambda row: int(row["chunk_id"])):
        row = dict(source)
        title = str(row.get("title") or "")
        match = NUMBERED_TITLE.match(title)
        parent_title = title
        if match:
            path = tuple(match.group(1).split("."))
            for length in range(len(path) - 1, 0, -1):
                ancestor = titles_by_path.get(path[:length])
                if ancestor:
                    parent_title = ancestor
                    break
            titles_by_path[path] = title

        content = str(row.get("content") or "")
        embedding_text = (
            f"{parent_title}\n\n{content}"
            if parent_title and parent_title != title
            else content
        )
        row["parent_title"] = parent_title
        row["embedding_text"] = embedding_text
        row["chunk_id"] = int(row["chunk_id"])
        row["part"] = int(row.get("part") or 0)
        row["item_name"] = str(row.get("item_name") or "")
        augmented.append(row)
    return augmented


def create_collection(client: Any, name: str, vector_dimension: int) -> None:
    schema = client.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunk_id", DataType.INT64, is_primary=True, auto_id=False)
    schema.add_field("content", DataType.VARCHAR, max_length=65535)
    schema.add_field("title", DataType.VARCHAR, max_length=100)
    schema.add_field("parent_title", DataType.VARCHAR, max_length=100)
    schema.add_field("embedding_text", DataType.VARCHAR, max_length=65535)
    schema.add_field("part", DataType.INT8)
    schema.add_field("file_title", DataType.VARCHAR, max_length=100)
    schema.add_field("item_name", DataType.VARCHAR, max_length=100)
    schema.add_field("sparse_vector", DataType.SPARSE_FLOAT_VECTOR)
    schema.add_field("dense_vector", DataType.FLOAT_VECTOR, dim=vector_dimension)

    indexes = client.prepare_index_params()
    indexes.add_index(
        field_name="dense_vector", index_name="dense_vector_index",
        index_type="AUTOINDEX", metric_type="COSINE",
    )
    indexes.add_index(
        field_name="sparse_vector", index_name="sparse_inverted_index",
        index_type="SPARSE_INVERTED_INDEX", metric_type="IP",
        params={"inverted_index_algo": "DAAT_MAXSCORE", "normalize": True, "quantization": "none"},
    )
    client.create_collection(collection_name=name, schema=schema, index_params=indexes)


def verify_and_write_samples(
    client: Any,
    baseline_rows: list[dict[str, Any]],
    experiment_collection: str,
    file_title: str,
) -> None:
    safe_title = escape_milvus_string(file_title)
    experiment_rows = client.query(
        collection_name=experiment_collection,
        filter=f'file_title == "{safe_title}"',
        output_fields=["chunk_id", "title", "parent_title", "embedding_text", "content", "file_title"],
        limit=200,
    )
    if len(experiment_rows) != 126:
        raise RuntimeError(f"experiment chunk count must be 126, got {len(experiment_rows)}")

    baseline_by_id = {str(row["chunk_id"]): row for row in baseline_rows}
    experiment_by_id = {str(row["chunk_id"]): row for row in experiment_rows}
    if set(baseline_by_id) != set(experiment_by_id):
        raise RuntimeError("experiment chunk_id set does not match baseline")
    mismatched_content = [
        chunk_id for chunk_id in baseline_by_id
        if baseline_by_id[chunk_id]["content"] != experiment_by_id[chunk_id]["content"]
    ]
    if mismatched_content:
        raise RuntimeError(f"content mismatch for chunk_ids: {mismatched_content}")

    hierarchical = [
        row for row in sorted(experiment_rows, key=lambda item: int(item["chunk_id"]))
        if row.get("parent_title") and row.get("parent_title") != row.get("title")
    ]
    if len(hierarchical) < 10:
        raise RuntimeError(f"expected at least 10 hierarchical chunks, got {len(hierarchical)}")
    samples = [
        {
            "chunk_id": str(row["chunk_id"]),
            "title": row["title"],
            "parent_title": row["parent_title"],
            "embedding_text": row["embedding_text"],
        }
        for row in hierarchical[:10]
    ]
    sample_path = Path(__file__).parent / "results" / "parent_context_samples.json"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"verified chunks: {len(experiment_rows)}")
    print(f"verified identical chunk_id set: {len(experiment_by_id)}")
    print("verified identical content: 126/126")
    print("parent inference inputs: ordered chunk titles only; dataset/Ground Truth not loaded")
    print(f"full sample audit: {sample_path.resolve()}")
    for sample in samples:
        preview = " ".join(sample["embedding_text"].split())[:240]
        print(f"\nchunk_id={sample['chunk_id']}")
        print(f"title={sample['title']}")
        print(f"parent_title={sample['parent_title']}")
        print(f"embedding_text={preview}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file-title", default=DEFAULT_FILE_TITLE)
    parser.add_argument("--experiment-collection", default=DEFAULT_EXPERIMENT_COLLECTION)
    args = parser.parse_args()

    if args.experiment_collection == milvus_config.chunks_collection:
        raise SystemExit("refusing to overwrite the baseline collection")
    client = get_milvus_client()
    if client.has_collection(args.experiment_collection):
        raise SystemExit(f"experiment collection already exists: {args.experiment_collection}")

    safe_title = escape_milvus_string(args.file_title)
    baseline_rows = client.query(
        collection_name=milvus_config.chunks_collection,
        filter=f'file_title == "{safe_title}"',
        output_fields=["chunk_id", "title", "parent_title", "part", "content", "file_title", "item_name"],
        limit=200,
    )
    if len(baseline_rows) != 126:
        raise RuntimeError(f"baseline chunk count must be 126, got {len(baseline_rows)}")

    augmented = infer_parent_context(baseline_rows)
    batch_size = 5
    for start in range(0, len(augmented), batch_size):
        batch = augmented[start:start + batch_size]
        vectors = generate_embeddings([row["embedding_text"] for row in batch])
        for index, row in enumerate(batch):
            row["dense_vector"] = vectors["dense"][index]
            row["sparse_vector"] = vectors["sparse"][index]

    create_collection(client, args.experiment_collection, len(augmented[0]["dense_vector"]))
    result = client.insert(collection_name=args.experiment_collection, data=augmented)
    if int(result.get("insert_count", 0)) != 126:
        raise RuntimeError(f"insert_count must be 126, got {result}")
    client.flush(collection_name=args.experiment_collection)
    verify_and_write_samples(client, baseline_rows, args.experiment_collection, args.file_title)


if __name__ == "__main__":
    main()
