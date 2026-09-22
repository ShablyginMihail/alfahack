from __future__ import annotations

import bisect
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Protocol

import structlog

from pii_guard.core.models import MaskResult, Span
from pii_guard.core.normalize import Document
from pii_guard.core.policy import Profile, apply_rules
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.service_words import SERVICE_WORDS

logger = structlog.get_logger()

WHOLE_PAYLOAD_MAX_CHARS = 120
WHOLE_PAYLOAD_MIN_SCORE = 0.2

_WORD_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*")


def resolve_overlaps(
    spans: Iterable[Span], priorities: Mapping[str, int] | None = None
) -> list[Span]:
    unique = {span: None for span in spans}
    ordered = sorted(
        unique,
        key=lambda span: (
            -span.score,
            -(span.end - span.start),
            -(priorities.get(span.pii_type, 0) if priorities else 0),
            span.start,
        ),
    )

    selected: list[Span] = []
    starts: list[int] = []
    ends: list[int] = []

    for span in ordered:
        idx = bisect.bisect_right(starts, span.start)
        overlaps = False
        if idx > 0 and ends[idx - 1] > span.start:
            overlaps = True
        if idx < len(starts) and starts[idx] < span.end:
            overlaps = True
        if overlaps:
            continue
        pos = bisect.bisect_left(starts, span.start)
        starts.insert(pos, span.start)
        ends.insert(pos, span.end)
        selected.append(span)

    selected.sort(key=lambda span: span.start)
    return selected


class Masker(Protocol):
    def apply(self, text: str, spans: Sequence[Span], profile: Profile) -> MaskResult: ...


class Engine:
    def __init__(
        self,
        registry: RecognizerRegistry,
        masker: Masker,
        priorities: Mapping[str, int] | None = None,
    ) -> None:
        self._registry = registry
        self._masker = masker
        self._priorities = priorities

    def analyze(self, text: str, profile: Profile) -> list[Span]:
        if not text:
            return []
        doc = Document.from_text(text)
        candidates: list[Span] = []
        for recognizer in self._registry.for_types(profile.pii_types):
            found: list[Span] = []
            try:
                found.extend(recognizer.find(doc))
            except Exception as exc:
                logger.warning(
                    "recognizer_failed",
                    recognizer=recognizer.name,
                    error_type=type(exc).__name__,
                )
                continue
            candidates.extend(found)

        threshold = profile.threshold_for
        filtered = [
            span
            for span in candidates
            if profile.allows(span.pii_type)
            and span.start < span.end
            and span.start >= 0
            and span.end <= len(text)
            and span.score >= threshold(span.pii_type)
        ]

        if len(text) <= WHOLE_PAYLOAD_MAX_CHARS:
            weak = [
                span
                for span in candidates
                if profile.allows(span.pii_type)
                and span.start < span.end
                and span.start >= 0
                and span.end <= len(text)
                and span.score >= WHOLE_PAYLOAD_MIN_SCORE
                and span.score < threshold(span.pii_type)
            ]
            if weak and self._whole_payload_covered(doc, candidates, profile):
                seen = set(filtered)
                for span in weak:
                    if span not in seen:
                        filtered.append(span)
                        seen.add(span)

        resolved = resolve_overlaps(filtered, self._priorities)
        return apply_rules(resolved, profile.rules)

    @staticmethod
    def _whole_payload_covered(
        doc: Document,
        candidates: list[Span],
        profile: Profile,
    ) -> bool:
        chars = list(doc.norm)
        for span in candidates:
            if (
                profile.allows(span.pii_type)
                and span.start < span.end
                and span.start >= 0
                and span.end <= len(doc.norm)
                and span.score >= WHOLE_PAYLOAD_MIN_SCORE
            ):
                for i in range(span.start, span.end):
                    chars[i] = " "
        words = _WORD_RE.findall("".join(chars))
        if not words:
            return True
        return all(word in SERVICE_WORDS for word in words)

    def mask(self, text: str, profile: Profile) -> MaskResult:
        spans = self.analyze(text, profile)
        return self._masker.apply(text, spans, profile)
