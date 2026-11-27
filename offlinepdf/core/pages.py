"""Page range parsing.

Users type 1-based page numbers; everything returned here is 0-based.

Accepted syntax (commas or semicolons between parts, spaces ignored):
    5        a single page
    2-4      pages 2, 3, 4
    7-       page 7 to the last page
    -3       first page to page 3
    6-4      a reversed range: 6, 5, 4
    end      the last page (also "last", "son")
"""

from __future__ import annotations

import re

from .errors import InvalidRangeError

_LAST_WORDS = {"end", "last", "son", "z"}
_PART_RE = re.compile(r"^(\w*)\s*(-?)\s*(\w*)$")


def _to_index(token: str, page_count: int, original: str) -> int:
    token = token.strip().lower()
    if token in _LAST_WORDS:
        return page_count - 1
    if not token.isdigit():
        raise InvalidRangeError(original)
    number = int(token)
    if number < 1 or number > page_count:
        raise InvalidRangeError(original, page_count=page_count)
    return number - 1


def parse_ranges(spec: str, page_count: int) -> list[list[int]]:
    """Parse ``spec`` into groups of 0-based page indices, one group per part."""
    if page_count < 1:
        raise InvalidRangeError(spec)
    spec = (spec or "").strip()
    if not spec:
        raise InvalidRangeError(spec)
    groups: list[list[int]] = []
    for raw in re.split(r"[,;]", spec):
        part = raw.strip()
        if not part:
            continue
        match = _PART_RE.match(part)
        if not match:
            raise InvalidRangeError(spec)
        left, dash, right = match.groups()
        if not dash:
            groups.append([_to_index(left, page_count, spec)])
            continue
        start = _to_index(left, page_count, spec) if left else 0
        stop = _to_index(right, page_count, spec) if right else page_count - 1
        step = 1 if stop >= start else -1
        groups.append(list(range(start, stop + step, step)))
    if not groups:
        raise InvalidRangeError(spec)
    return groups


def parse_selection(spec: str, page_count: int) -> list[int]:
    """Flatten ``spec`` into unique page indices, keeping the typed order."""
    seen: set[int] = set()
    result: list[int] = []
    for group in parse_ranges(spec, page_count):
        for index in group:
            if index not in seen:
                seen.add(index)
                result.append(index)
    return result


def format_selection(indices: list[int]) -> str:
    """Turn 0-based indices into a compact 1-based spec, e.g. [0,1,2,5] -> "1-3, 6"."""
    ordered = sorted(set(indices))
    parts: list[str] = []
    i = 0
    while i < len(ordered):
        start = ordered[i]
        while i + 1 < len(ordered) and ordered[i + 1] == ordered[i] + 1:
            i += 1
        stop = ordered[i]
        parts.append(str(start + 1) if start == stop else f"{start + 1}-{stop + 1}")
        i += 1
    return ", ".join(parts)
