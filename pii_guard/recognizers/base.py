from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from pii_guard.core.context import find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.validators import digits


@dataclass(frozen=True, slots=True)
class PatternRule:
    pii_type: str
    regex: re.Pattern[str]
    base_score: float
    group: int | str = 0
    validator: Callable[[str], bool] | None = None
    validator_bonus: float = 0.0
    context: re.Pattern[str] | None = None
    context_bonus: float = 0.0
    context_window: int = 40
    negative: re.Pattern[str] | None = None
    negative_penalty: float = 0.0


class RegexRecognizer(Recognizer):
    def __init__(self, name: str, rules: Sequence[PatternRule]) -> None:
        self.name = name
        self._rules = tuple(rules)
        self.pii_types = frozenset(rule.pii_type for rule in self._rules)

    def find(self, doc: Document) -> Iterable[Span]:
        spans: list[Span] = []
        for rule in self._rules:
            for match in rule.regex.finditer(doc.norm):
                value = match.group(rule.group)
                if value is None:
                    continue
                start = match.start(rule.group)
                end = match.end(rule.group)
                score = rule.base_score
                if rule.validator is not None and rule.validator(digits(value)):
                    score += rule.validator_bonus
                if (
                    rule.context is not None
                    and find_keyword(doc, start, end, rule.context, rule.context_window, "both")
                    is not None
                ):
                    score += rule.context_bonus
                if (
                    rule.negative is not None
                    and find_keyword(doc, start, end, rule.negative, rule.context_window, "before")
                    is not None
                ):
                    score -= rule.negative_penalty
                score = max(0.0, min(1.0, score))
                spans.append(
                    Span(
                        start=start,
                        end=end,
                        pii_type=rule.pii_type,
                        score=score,
                        recognizer=self.name,
                    )
                )
        return spans
