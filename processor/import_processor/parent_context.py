"""Infer parent headings for chunks from document structure only."""

from __future__ import annotations

import re
from typing import Any, Iterable


MARKDOWN_HEADING = re.compile(r"^\s*(#{1,6})\s+(.+?)\s*$")
NUMBERED_HEADING = re.compile(r"^(\d+(?:\.\d+)*)\s+.+$")


def _heading_parts(title: str) -> tuple[int, str] | None:
    match = MARKDOWN_HEADING.match(title or "")
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def _number_path(heading_text: str) -> tuple[str, ...] | None:
    match = NUMBERED_HEADING.match(heading_text)
    return tuple(match.group(1).split(".")) if match else None


def assign_parent_titles(chunks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return copied chunks with a parent title inferred from prior real headings.

    Markdown heading levels are authoritative. Number paths are a fallback for
    converters that flatten headings such as ``2.4`` and ``2.4.3`` to the same
    Markdown level. A parent is selected only from a heading already observed in
    the current document; no title text is synthesized.
    """

    heading_stack: dict[int, str] = {}
    numbered_titles: dict[tuple[str, ...], str] = {}
    output: list[dict[str, Any]] = []

    for source_chunk in chunks:
        chunk = source_chunk.copy()
        title = str(chunk.get("title") or "")
        existing_parent = str(chunk.get("parent_title") or "")

        # Long-section fragments have synthetic titles ("... - 1") but retain
        # the real source heading in parent_title. Keep that real document title.
        fragment_heading = _heading_parts(existing_parent) if chunk.get("part") else None
        if fragment_heading:
            chunk["parent_title"] = existing_parent
            output.append(chunk)
            fragment_level, fragment_text = fragment_heading
            heading_stack[fragment_level] = existing_parent
            for deeper_level in tuple(key for key in heading_stack if key > fragment_level):
                del heading_stack[deeper_level]
            fragment_path = _number_path(fragment_text)
            if fragment_path:
                numbered_titles[fragment_path] = existing_parent
            continue

        heading = _heading_parts(title)
        if not heading:
            chunk["parent_title"] = ""
            output.append(chunk)
            continue

        level, heading_text = heading
        markdown_parent = next(
            (heading_stack[parent_level] for parent_level in range(level - 1, 0, -1)
             if parent_level in heading_stack),
            "",
        )

        number_path = _number_path(heading_text)
        numbered_parent = ""
        if number_path:
            for length in range(len(number_path) - 1, 0, -1):
                numbered_parent = numbered_titles.get(number_path[:length], "")
                if numbered_parent:
                    break

        # A discovered numbered ancestor is more specific when Markdown levels
        # were flattened; otherwise the actual Markdown hierarchy is used.
        chunk["parent_title"] = numbered_parent or markdown_parent
        output.append(chunk)

        heading_stack[level] = title
        for deeper_level in tuple(key for key in heading_stack if key > level):
            del heading_stack[deeper_level]
        if number_path:
            numbered_titles[number_path] = title

    return output


def build_embedding_text(chunk: dict[str, Any]) -> str:
    """Build vector input without mutating or replacing the stored content."""

    content = str(chunk["content"])
    item_name = str(chunk.get("item_name") or "")
    original_embedding_text = f"{item_name}\n{content}" if item_name else content
    parent_title = str(chunk.get("parent_title") or "").strip()
    if not parent_title:
        return original_embedding_text
    return f"{parent_title}\n\n{original_embedding_text}"
