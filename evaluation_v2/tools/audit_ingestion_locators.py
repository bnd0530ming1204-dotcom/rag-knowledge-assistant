"""Read-only audit that source locators survive the current production chunker.

This is not used to choose labels. It only verifies that already-authored source
locators remain observable after heading-aware splitting.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from processor.import_processor.nodes.d_node_document_split import NodeDocumentSplit
from processor.import_processor.parent_context import assign_parent_titles


LOCATOR = re.compile(r"<!-- locator: ([A-Z0-9-]+) -->")


def main() -> None:
    node = NodeDocumentSplit()
    errors = []
    total_locators = 0
    total_chunks = 0
    for path in sorted((PROJECT_ROOT / "evaluation_v2" / "documents").glob("*.md")):
        content = path.read_text(encoding="utf-8")
        expected = LOCATOR.findall(content)
        sections, title_count, _ = node._step_2_split_by_title(content, path.stem)
        sections = node._step_3_handle_no_title(content, sections, title_count, path.stem)
        chunks = assign_parent_titles(node._step_4_refine_chunks(sections))
        observed = [item for chunk in chunks for item in LOCATOR.findall(chunk.get("content", ""))]
        total_locators += len(expected)
        total_chunks += len(chunks)
        if sorted(expected) != sorted(observed):
            errors.append(f"{path.name}: expected={sorted(expected)} observed={sorted(observed)}")
        duplicates = [item for item in set(observed) if observed.count(item) != 1]
        if duplicates:
            errors.append(f"{path.name}: duplicated locators after chunking: {duplicates}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {total_locators} locators survived current chunking exactly once across {total_chunks} chunks")


if __name__ == "__main__":
    main()

