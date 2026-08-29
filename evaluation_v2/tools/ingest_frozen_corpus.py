"""Ingest the frozen corpus into an isolated Milvus collection.

Uses the current production chunker, parent-heading embedding input, BGE-M3
dense/sparse encoder, and production Milvus schema/index creation method.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
EVAL_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.embedding_config import embedding_config
from processor.import_processor.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.f_node_bge_embedding import NodeBGEEmbedding
from processor.import_processor.nodes.g_node_import_milvus import NodeImportMilvus
from processor.import_processor.parent_context import assign_parent_titles
from utils.milvus_utils import get_milvus_client


DEFAULT_COLLECTION = "rag_eval_v2_chunks"
MANIFEST = EVAL_ROOT / "artifacts" / "manifest_frozen.json"
OUTPUT = EVAL_ROOT / "artifacts" / "ingestion_frozen.json"


def verify_frozen_documents(manifest: dict) -> list[tuple[dict, Path]]:
    verified = []
    for item in manifest["documents"]:
        path = EVAL_ROOT / item["file"]
        payload = path.read_bytes()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != item["sha256"]:
            raise RuntimeError(f"frozen document hash mismatch: {path}")
        verified.append((item, path))
    return verified


def split_document(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8")
    splitter = NodeDocumentSplit()
    sections, title_count, _ = splitter._step_2_split_by_title(content, path.stem)
    sections = splitter._step_3_handle_no_title(content, sections, title_count, path.stem)
    sections = splitter._step_4_refine_chunks(sections)
    return assign_parent_titles(sections)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    if args.collection != DEFAULT_COLLECTION:
        raise SystemExit(f"Evaluation V2 collection must be exactly {DEFAULT_COLLECTION!r}")

    started = time.perf_counter()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    verified = verify_frozen_documents(manifest)
    client = get_milvus_client()
    if client.has_collection(args.collection):
        raise SystemExit(
            f"Refusing to overwrite existing isolated collection {args.collection!r}. "
            "Inspect it manually before any destructive action."
        )

    all_chunks = []
    document_rows = []
    errors = []
    for doc_meta, path in verified:
        doc_started = time.perf_counter()
        try:
            split_started = time.perf_counter()
            chunks = split_document(path)
            split_ms = (time.perf_counter() - split_started) * 1000
            for chunk in chunks:
                chunk["document_id"] = doc_meta["document_id"]
                chunk["source_locator"] = re.findall(
                    r"<!-- locator: ([A-Z0-9-]+) -->", chunk.get("content", "")
                )
                chunk["section_path"] = [
                    value for value in (chunk.get("parent_title"), chunk.get("title")) if value
                ]
                chunk.setdefault("part", 0)
            embedding_started = time.perf_counter()
            embedded = NodeBGEEmbedding()._step_generate_embeddings(chunks)
            embedding_ms = (time.perf_counter() - embedding_started) * 1000
            all_chunks.extend(embedded)
            document_rows.append({
                "document_id": doc_meta["document_id"],
                "file": doc_meta["file"],
                "chunk_count": len(embedded),
                "split_latency_ms": round(split_ms, 3),
                "embedding_latency_ms": round(embedding_ms, 3),
                "total_latency_ms": round((time.perf_counter() - doc_started) * 1000, 3),
            })
        except Exception as exc:
            errors.append({"document_id": doc_meta["document_id"], "error": f"{type(exc).__name__}: {exc}"})
            break

    if errors:
        result = {
            "status": "FAILED_BEFORE_COLLECTION_CREATE",
            "collection": args.collection,
            "document_count": len(verified),
            "processed_document_count": len(document_rows),
            "errors": errors,
            "documents": document_rows,
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise SystemExit(json.dumps(errors, ensure_ascii=False))
    if not all_chunks:
        raise SystemExit("No chunks generated")

    vector_dimension = len(all_chunks[0]["dense_vector"])
    NodeImportMilvus().create_chunks_collection(client, args.collection, vector_dimension)
    insert_result = client.insert(collection_name=args.collection, data=all_chunks)
    client.load_collection(args.collection)
    stats = client.get_collection_stats(args.collection)
    row_count = int(stats.get("row_count", insert_result.get("insert_count", 0)))
    result = {
        "status": "COMPLETED",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "collection": args.collection,
        "document_count": len(verified),
        "chunk_count": len(all_chunks),
        "insert_count": insert_result.get("insert_count"),
        "collection_row_count": row_count,
        "embedding_model": embedding_config.bge_m3,
        "embedding_model_path_configured": bool(embedding_config.bge_m3_path),
        "embedding_device": embedding_config.bge_device,
        "vector_dimension": vector_dimension,
        "errors": errors,
        "documents": document_rows,
        "total_ingestion_latency_ms": round((time.perf_counter() - started) * 1000, 3),
        "configuration": "CURRENT PRODUCTION CHUNKING/PARENT CONTEXT/BGE-M3/MILVUS SCHEMA; NO EVALUATION TUNING",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

