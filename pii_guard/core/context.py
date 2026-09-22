from __future__ import annotations

import re
from collections.abc import Iterable

from pii_guard.core.normalize import Document, normalize


def compile_keywords(words: Iterable[str]) -> re.Pattern[str]:
    normalized = sorted({normalize(word) for word in words}, key=len, reverse=True)
    alternatives = "|".join(re.escape(word) for word in normalized)
    return re.compile(rf"(?<!\w)(?:{alternatives})\w*")


def find_keyword(
    doc: Document,
    start: int,
    end: int,
    pattern: re.Pattern[str],
    window: int = 40,
    direction: str = "before",
) -> int | None:
    norm = doc.norm
    if direction == "before":
        lo = max(0, start - window)
        matches = list(pattern.finditer(norm, lo, start))
        if not matches:
            return None
        return start - matches[-1].start()
    if direction == "after":
        hi = min(len(norm), end + window)
        match = pattern.search(norm, end, hi)
        if match is None:
            return None
        return match.start() - end
    if direction == "both":
        before = find_keyword(doc, start, end, pattern, window, "before")
        after = find_keyword(doc, start, end, pattern, window, "after")
        if before is None:
            return after
        if after is None:
            return before
        return min(before, after)
    raise ValueError(f"unknown direction: {direction!r}")


def has_keyword(
    doc: Document,
    start: int,
    end: int,
    pattern: re.Pattern[str],
    window: int = 40,
    direction: str = "before",
) -> bool:
    return find_keyword(doc, start, end, pattern, window, direction) is not None
