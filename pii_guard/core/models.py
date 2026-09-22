from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Span:
    start: int
    end: int
    pii_type: str
    score: float
    recognizer: str
    part: str | None = None


@dataclass(frozen=True, slots=True)
class Replacement:
    start: int
    end: int
    masked_start: int
    original: str
    masked: str
    pii_type: str


@dataclass(frozen=True, slots=True)
class MaskResult:
    text: str
    replacements: tuple[Replacement, ...]

    def type_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for replacement in self.replacements:
            counts[replacement.pii_type] = counts.get(replacement.pii_type, 0) + 1
        return counts


@dataclass(frozen=True, slots=True)
class MappingRecord:
    original_fp: str
    masked_text: str
    replacements: tuple[Replacement, ...]
