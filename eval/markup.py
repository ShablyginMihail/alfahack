from __future__ import annotations

from dataclasses import dataclass

from pii_guard.core.types import default_type_registry


@dataclass(frozen=True, slots=True)
class GoldSpan:
    start: int
    end: int
    pii_type: str


def parse_markup(line: str) -> tuple[str, list[GoldSpan]]:
    valid_types = default_type_registry().codes()
    parts: list[str] = []
    spans: list[GoldSpan] = []
    cursor = 0
    pos = 0
    i = 0
    while i < len(line):
        if not line.startswith("[[", i):
            i += 1
            continue
        end = line.find("]]", i + 2)
        if end == -1:
            raise ValueError(f"broken markup at position {i}")
        inner = line[i + 2 : end]
        colon = inner.find(":")
        if colon == -1:
            raise ValueError(f"broken markup at position {i}")
        pii_type = inner[:colon]
        value = inner[colon + 1 :]
        if pii_type not in valid_types:
            raise ValueError(f"unknown type {pii_type!r} at position {i}")
        parts.append(line[cursor:i])
        pos += i - cursor
        parts.append(value)
        spans.append(GoldSpan(pos, pos + len(value), pii_type))
        pos += len(value)
        cursor = end + 2
        i = end + 2
    parts.append(line[cursor:])
    return "".join(parts), spans
