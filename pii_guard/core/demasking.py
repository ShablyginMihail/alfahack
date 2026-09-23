from __future__ import annotations

import re
from collections.abc import Sequence

from pii_guard.core.models import MappingRecord, Replacement


def restore(masked_text: str, replacements: Sequence[Replacement]) -> str | None:
    ordered = sorted(replacements, key=lambda r: r.masked_start)
    parts: list[str] = []
    cursor = 0
    for replacement in ordered:
        if replacement.masked_start < cursor:
            return None
        masked = replacement.masked
        end = replacement.masked_start + len(masked)
        if masked_text[replacement.masked_start : end] != masked:
            return None
        parts.append(masked_text[cursor : replacement.masked_start])
        parts.append(replacement.original)
        cursor = end
    parts.append(masked_text[cursor:])
    return "".join(parts)


def contains_masked_fragments(text: str, replacements: Sequence[Replacement]) -> bool:
    for replacement in replacements:
        masked = replacement.masked
        if not masked:
            continue
        if not any(ch.isalnum() for ch in masked):
            continue
        if masked in text:
            return True
    return False


def replace_masked_fragments(text: str, replacements: Sequence[Replacement]) -> str:
    by_masked: dict[str, list[str]] = {}
    for replacement in replacements:
        masked = replacement.masked
        if not masked:
            continue
        if not any(ch.isalnum() for ch in masked):
            continue
        by_masked.setdefault(masked, []).append(replacement.original)

    if not by_masked:
        return text

    pattern = "|".join(re.escape(masked) for masked in sorted(by_masked, key=len, reverse=True))

    def substitute(match: re.Match[str]) -> str:
        masked = match.group(0)
        originals = by_masked[masked]
        original = originals.pop(0) if len(originals) > 1 else originals[0]
        return original

    return re.sub(pattern, substitute, text)


def unmask(text: str, record: MappingRecord) -> str:
    if text == record.masked_text:
        restored = restore(record.masked_text, record.replacements)
        if restored is not None:
            return restored
    return replace_masked_fragments(text, record.replacements)
