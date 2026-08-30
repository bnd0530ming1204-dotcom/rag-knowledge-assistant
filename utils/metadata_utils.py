"""Stable chunk metadata contract with legacy Milvus compatibility."""
from __future__ import annotations

import hashlib
from typing import Any


def normalize_chunk_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    doc = dict(raw or {})
    document_name = str(doc.get("document_name") or doc.get("file_title") or "").strip()
    document_id = str(doc.get("document_id") or "").strip()
    if not document_id and document_name:
        document_id = hashlib.sha256(document_name.encode("utf-8")).hexdigest()[:16]
    title = str(doc.get("title") or "").strip()
    normalized = {
        **doc,
        "document_id": document_id,
        "document_name": document_name,
        "file_title": str(doc.get("file_title") or document_name).strip(),
        "chunk_id": str(doc.get("chunk_id") or ""),
        "title": title,
        "section_title": str(doc.get("section_title") or title).strip(),
        "parent_title": str(doc.get("parent_title") or "").strip(),
        "content": str(doc.get("content") or ""),
    }
    # Page is copied only when upstream supplied a real value.
    if "page" not in doc:
        normalized.pop("page", None)
    return normalized
