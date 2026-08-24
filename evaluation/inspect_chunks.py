"""Read-only helper for manually locating Ground Truth chunks in Milvus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.milvus_config import milvus_config  # noqa: E402
from utils.milvus_utils import escape_milvus_string, get_milvus_client  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file-title", help="Exact file_title; omit to list available files")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--preview-chars", type=int, default=300)
    args = parser.parse_args()
    if args.limit < 1 or args.preview_chars < 1:
        parser.error("--limit and --preview-chars must be positive")

    client = get_milvus_client()
    if not args.file_title:
        rows = client.query(
            collection_name=milvus_config.chunks_collection,
            filter="",
            output_fields=["file_title"],
            limit=args.limit,
        )
        titles = sorted({str(row.get("file_title", "")) for row in rows})
        print("Available file_title values (limited query):")
        for title in titles:
            print(f"  {title}")
        print("\nRun again with: python evaluation/inspect_chunks.py --file-title \"...\"")
        return

    safe_title = escape_milvus_string(args.file_title)
    rows = client.query(
        collection_name=milvus_config.chunks_collection,
        filter=f'file_title == "{safe_title}"',
        output_fields=["chunk_id", "file_title", "title", "content"],
        limit=args.limit,
    )
    print(f"file_title={args.file_title!r}, chunks shown={len(rows)}")
    for row in rows:
        content = " ".join(str(row.get("content", "")).split())
        print(f"\nchunk_id: {row.get('chunk_id')}")
        print(f"title: {row.get('title', '')}")
        print(f"content: {content[:args.preview_chars]}")


if __name__ == "__main__":
    main()
