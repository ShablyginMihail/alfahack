from __future__ import annotations

from collections.abc import Iterable

from pii_guard.core.engine import Engine, resolve_overlaps
from pii_guard.core.models import MaskResult, Replacement, Span
from pii_guard.core.normalize import Document
from pii_guard.core.policy import CombinationRule, Profile
from pii_guard.core.registry import Recognizer, RecognizerRegistry
from tests.helpers import PARTIAL_PROFILE


class FakeRecognizer:
    def __init__(self, name: str, pii_types: frozenset[str], spans: list[Span]) -> None:
        self.name = name
        self.pii_types = pii_types
        self._spans = spans

    def find(self, doc: Document) -> Iterable[Span]:
        return self._spans


class FailingRecognizer:
    name = "failing"
    pii_types = frozenset({"PIN"})

    def find(self, doc: Document) -> Iterable[Span]:
        raise RuntimeError("boom")


class GeneratorFailingRecognizer:
    name = "gen_failing"
    pii_types = frozenset({"PIN"})

    def find(self, doc: Document) -> Iterable[Span]:
        yield _span(0, 4, "PIN", 0.9, name="gen_failing")
        raise RuntimeError("boom")


class LabelMasker:
    def apply(self, text: str, spans: list[Span], profile: Profile) -> MaskResult:
        replacements: list[Replacement] = []
        masked = text
        for span in sorted(spans, key=lambda s: s.start, reverse=True):
            masked = masked[: span.start] + f"[{span.pii_type}]" + masked[span.end :]
            replacements.append(
                Replacement(
                    start=span.start,
                    end=span.end,
                    masked_start=span.start,
                    original=text[span.start : span.end],
                    masked=f"[{span.pii_type}]",
                    pii_type=span.pii_type,
                )
            )
        return MaskResult(masked, tuple(replacements))


def _span(start: int, end: int, pii_type: str, score: float, name: str = "r") -> Span:
    return Span(start=start, end=end, pii_type=pii_type, score=score, recognizer=name)


def _registry(*recognizers: Recognizer) -> RecognizerRegistry:
    registry = RecognizerRegistry()
    for recognizer in recognizers:
        registry.register(recognizer)
    return registry


def test_overlap_higher_score_wins() -> None:
    spans = [
        _span(0, 5, "PHONE", 0.6),
        _span(2, 8, "PHONE", 0.9),
    ]
    result = resolve_overlaps(spans)
    assert result == [_span(2, 8, "PHONE", 0.9)]


def test_overlap_equal_score_longer_wins() -> None:
    spans = [
        _span(0, 5, "PHONE", 0.9),
        _span(2, 8, "PHONE", 0.9),
    ]
    result = resolve_overlaps(spans)
    assert result == [_span(2, 8, "PHONE", 0.9)]


def test_nested_span() -> None:
    spans = [
        _span(0, 10, "CARD_NUMBER", 0.9),
        _span(3, 6, "PIN", 0.95),
    ]
    result = resolve_overlaps(spans)
    assert result == [_span(3, 6, "PIN", 0.95)]


def test_adjacent_spans_both_kept() -> None:
    spans = [
        _span(0, 3, "PHONE", 0.9),
        _span(3, 6, "PHONE", 0.9),
    ]
    result = resolve_overlaps(spans)
    assert result == [_span(0, 3, "PHONE", 0.9), _span(3, 6, "PHONE", 0.9)]


def test_duplicates_collapsed() -> None:
    spans = [
        _span(0, 5, "PHONE", 0.9),
        _span(0, 5, "PHONE", 0.9),
    ]
    result = resolve_overlaps(spans)
    assert result == [_span(0, 5, "PHONE", 0.9)]


def test_analyze_threshold_filters_weak_spans() -> None:
    registry = _registry(
        FakeRecognizer(
            "r",
            frozenset({"PHONE"}),
            [_span(0, 5, "PHONE", 0.9), _span(6, 10, "PHONE", 0.2)],
        )
    )
    engine = Engine(registry, LabelMasker())
    result = engine.analyze("12345 67890", PARTIAL_PROFILE)
    assert result == [_span(0, 5, "PHONE", 0.9)]


def test_analyze_strict_lowers_threshold() -> None:
    registry = _registry(FakeRecognizer("r", frozenset({"PHONE"}), [_span(0, 5, "PHONE", 0.4)]))
    engine = Engine(registry, LabelMasker())
    assert engine.analyze("12345", PARTIAL_PROFILE) == []
    strict = Profile(name="strict", strict=True)
    assert engine.analyze("12345", strict) == [_span(0, 5, "PHONE", 0.4)]


def test_analyze_filters_pii_types() -> None:
    registry = _registry(
        FakeRecognizer(
            "r",
            frozenset({"PHONE", "EMAIL"}),
            [_span(0, 5, "PHONE", 0.9), _span(6, 10, "EMAIL", 0.9)],
        )
    )
    engine = Engine(registry, LabelMasker())
    profile = Profile(name="p", pii_types=frozenset({"EMAIL"}))
    result = engine.analyze("12345 a@b.c", profile)
    assert result == [_span(6, 10, "EMAIL", 0.9)]


def test_analyze_rule_pin_requires_card() -> None:
    rule = CombinationRule("PIN", frozenset({"CARD_NUMBER"}))
    profile = Profile(name="p", rules=(rule,))
    registry = _registry(FakeRecognizer("r", frozenset({"PIN"}), [_span(0, 4, "PIN", 0.9)]))
    engine = Engine(registry, LabelMasker())
    assert engine.analyze("1234", profile) == []

    registry2 = _registry(
        FakeRecognizer(
            "r",
            frozenset({"PIN", "CARD_NUMBER"}),
            [_span(0, 4, "PIN", 0.9), _span(5, 10, "CARD_NUMBER", 0.9)],
        )
    )
    engine2 = Engine(registry2, LabelMasker())
    result = engine2.analyze("1234 56789", profile)
    assert {span.pii_type for span in result} == {"PIN", "CARD_NUMBER"}


def test_analyze_drops_out_of_bounds_spans() -> None:
    registry = _registry(FakeRecognizer("r", frozenset({"PHONE"}), [_span(0, 50, "PHONE", 0.9)]))
    engine = Engine(registry, LabelMasker())
    assert engine.analyze("12345", PARTIAL_PROFILE) == []


def test_analyze_failing_recognizer_does_not_break() -> None:
    registry = _registry(
        FailingRecognizer(),
        FakeRecognizer("ok", frozenset({"PHONE"}), [_span(0, 5, "PHONE", 0.9)]),
    )
    engine = Engine(registry, LabelMasker())
    result = engine.analyze("12345", PARTIAL_PROFILE)
    assert result == [_span(0, 5, "PHONE", 0.9)]


def test_analyze_generator_recognizer_failure_discards_partial_spans() -> None:
    registry = _registry(
        GeneratorFailingRecognizer(),
        FakeRecognizer("ok", frozenset({"PHONE"}), [_span(0, 5, "PHONE", 0.9)]),
    )
    engine = Engine(registry, LabelMasker())
    result = engine.analyze("12345", PARTIAL_PROFILE)
    assert result == [_span(0, 5, "PHONE", 0.9)]


def test_mask_returns_masker_result() -> None:
    registry = _registry(FakeRecognizer("r", frozenset({"PHONE"}), [_span(0, 5, "PHONE", 0.9)]))
    engine = Engine(registry, LabelMasker())
    result = engine.mask("12345", PARTIAL_PROFILE)
    assert result.text == "[PHONE]"
    assert result.replacements[0].pii_type == "PHONE"


def test_mask_empty_text() -> None:
    engine = Engine(_registry(), LabelMasker())
    result = engine.mask("", PARTIAL_PROFILE)
    assert result == MaskResult("", ())
