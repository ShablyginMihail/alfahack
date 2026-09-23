from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from pii_guard.core.models import Span

_MIN_THRESHOLD = 0.05


@dataclass(frozen=True, slots=True)
class CombinationRule:
    pii_type: str
    requires_any: frozenset[str]
    window: int = 300


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    pii_types: frozenset[str] | None = None
    mask_style: str = "partial"
    unmask: bool = True
    strict: bool = False
    rules: tuple[CombinationRule, ...] = ()
    thresholds: Mapping[str, float] = field(default_factory=dict)
    default_threshold: float = 0.5
    strict_delta: float = 0.15
    irreversible: frozenset[str] = frozenset()

    def allows(self, pii_type: str) -> bool:
        return self.pii_types is None or pii_type in self.pii_types

    def threshold_for(self, pii_type: str) -> float:
        threshold = self.thresholds.get(pii_type, self.default_threshold)
        if self.strict:
            threshold -= self.strict_delta
        return max(threshold, _MIN_THRESHOLD)


CHECKER_PROFILE = Profile(name="checker", mask_style="full")


def _distance(a: Span, b: Span) -> int:
    if a.start < b.end and b.start < a.end:
        return 0
    if a.end <= b.start:
        return b.start - a.end
    return a.start - b.end


def apply_rules(spans: Sequence[Span], rules: Sequence[CombinationRule]) -> list[Span]:
    if not rules:
        return list(spans)

    present = {span.pii_type for span in spans}
    kept: list[Span] = []
    for span in spans:
        for rule in rules:
            if rule.pii_type != span.pii_type:
                continue
            if not (rule.requires_any & present):
                break
            if not any(
                _distance(span, other) <= rule.window
                for other in spans
                if other.pii_type in rule.requires_any
            ):
                break
        else:
            kept.append(span)
    return kept
