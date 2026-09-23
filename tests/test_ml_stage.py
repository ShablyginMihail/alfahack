from __future__ import annotations

from collections.abc import Sequence

from pii_guard.config.loader import load_config
from pii_guard.core.engine import Engine
from pii_guard.core.ml_stage import MlStage
from pii_guard.core.models import MaskResult, Replacement, Span
from pii_guard.core.normalize import Document
from pii_guard.core.policy import Profile
from pii_guard.core.registry import Recognizer, RecognizerRegistry
from pii_guard.observability.metrics import metrics
from tests.helpers import PARTIAL_PROFILE, write_config

PERSON = "PERSON"
ADDRESS = "ADDRESS"
PHONE = "PHONE"
FAKE_NER = "fake_ner"
PERSON_TEXT = "Иванов Иван"
OUTCOME_OK = "ok"
OUTCOME_LONG = "long"
OUTCOME_COVERED = "covered"
OUTCOME_BUSY = "busy"
OUTCOME_ERROR = "error"
OUTCOME_UNAVAILABLE = "unavailable"


class FakeNerRecognizer:
    name = FAKE_NER
    pii_types = frozenset({PERSON, ADDRESS})

    def __init__(self, spans: list[Span] | None = None, error: Exception | None = None) -> None:
        self._spans = spans or []
        self._error = error
        self.calls = 0

    def find(self, doc: Document) -> list[Span]:
        self.calls += 1
        if self._error is not None:
            raise self._error
        return list(self._spans)


class FakeRuleRecognizer:
    name = "rule"
    pii_types = frozenset({PERSON})

    def __init__(self, spans: list[Span] | None = None) -> None:
        self._spans = spans or []

    def find(self, doc: Document) -> list[Span]:
        return list(self._spans)


class LabelMasker:
    def apply(self, text: str, spans: Sequence[Span], profile: Profile) -> MaskResult:
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


def _span(start: int, end: int, pii_type: str, score: float, name: str = FAKE_NER) -> Span:
    return Span(start=start, end=end, pii_type=pii_type, score=score, recognizer=name)


def _registry(*recognizers: Recognizer) -> RecognizerRegistry:
    registry = RecognizerRegistry()
    for recognizer in recognizers:
        registry.register(recognizer)
    return registry


def _ner_count(outcome: str) -> float:
    return metrics.ner_total.labels(outcome=outcome)._value.get()


def _assert_outcome(outcome: str, before: float) -> None:
    assert _ner_count(outcome) == before + 1


def test_outcome_ok() -> None:
    before = _ner_count(OUTCOME_OK)
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [])
    assert result == [_span(0, 10, PERSON, 0.9)]
    _assert_outcome(OUTCOME_OK, before)


def test_outcome_long() -> None:
    before = _ner_count(OUTCOME_LONG)
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer, max_chars=5)
    result = ml.run(Document.from_text(PERSON_TEXT), [])
    assert result == []
    assert recognizer.calls == 0
    _assert_outcome(OUTCOME_LONG, before)


def test_outcome_covered() -> None:
    before = _ner_count(OUTCOME_COVERED)
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [_span(0, 10, PERSON, 0.9)])
    assert result == []
    assert recognizer.calls == 0
    _assert_outcome(OUTCOME_COVERED, before)


def test_outcome_busy() -> None:
    before = _ner_count(OUTCOME_BUSY)
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer, concurrency=0, wait_ms=5)
    result = ml.run(Document.from_text(PERSON_TEXT), [])
    assert result == []
    assert recognizer.calls == 0
    _assert_outcome(OUTCOME_BUSY, before)


def test_outcome_error() -> None:
    before = _ner_count(OUTCOME_ERROR)
    recognizer = FakeNerRecognizer(error=RuntimeError("boom"))
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [])
    assert result == []
    _assert_outcome(OUTCOME_ERROR, before)


def test_outcome_unavailable() -> None:
    before = _ner_count(OUTCOME_UNAVAILABLE)
    recognizer = FakeNerRecognizer(error=RuntimeError("boom"))
    ml = MlStage(recognizer)
    ml.warm_up()
    result = ml.run(Document.from_text(PERSON_TEXT), [])
    assert result == []
    _assert_outcome(OUTCOME_UNAVAILABLE, before)


def test_warm_up_calls_recognizer() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer)
    ml.warm_up()
    assert recognizer.calls == 1


def test_voting_adds_bonus() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.5)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [_span(0, 10, PERSON, 0.3)])
    assert result == [_span(0, 10, PERSON, 0.7)]


def test_voting_caps_at_one() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [_span(0, 10, PERSON, 0.3)])
    assert result == [_span(0, 10, PERSON, 1.0)]


def test_voting_skipped_low_rule_score() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.5)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [_span(0, 10, PERSON, 0.1)])
    assert result == [_span(0, 10, PERSON, 0.5)]


def test_voting_skipped_different_type() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.5)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [_span(0, 10, ADDRESS, 0.3)])
    assert result == [_span(0, 10, PERSON, 0.5)]


def test_model_dropped_overlapping_rule_other_type() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(2, 11, ADDRESS, 0.7)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT), [_span(0, 11, PHONE, 0.6)])
    assert result == []


def test_model_kept_not_overlapping_rule_other_type() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(12, 22, ADDRESS, 0.7)])
    ml = MlStage(recognizer)
    result = ml.run(Document.from_text(PERSON_TEXT + " " + PERSON_TEXT), [_span(0, 11, PHONE, 0.6)])
    assert result == [_span(12, 22, ADDRESS, 0.7)]


def test_profile_ner_false_does_not_call_model() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer)
    engine = Engine(_registry(), LabelMasker(), ml=ml)
    profile = Profile(name="p", ner=False)
    engine.analyze(PERSON_TEXT, profile)
    assert recognizer.calls == 0


def test_model_candidates_pass_threshold() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    ml = MlStage(recognizer)
    engine = Engine(_registry(), LabelMasker(), ml=ml)
    profile = Profile(name="p", ner=True)
    result = engine.analyze(PERSON_TEXT, profile)
    assert result == [_span(0, 10, PERSON, 0.9)]


def test_model_candidates_resolve_overlaps() -> None:
    recognizer = FakeNerRecognizer(spans=[_span(0, 10, PERSON, 0.9), _span(2, 8, PERSON, 0.95)])
    ml = MlStage(recognizer)
    engine = Engine(_registry(), LabelMasker(), ml=ml)
    profile = Profile(name="p", ner=True)
    result = engine.analyze(PERSON_TEXT, profile)
    assert result == [_span(2, 8, PERSON, 0.95)]


def test_model_candidate_combined_with_rules() -> None:
    rule = FakeRuleRecognizer(spans=[_span(0, 10, PERSON, 0.9)])
    recognizer = FakeNerRecognizer(spans=[_span(12, 22, PERSON, 0.8)])
    ml = MlStage(recognizer)
    engine = Engine(_registry(rule), LabelMasker(), ml=ml)
    profile = Profile(name="p", ner=True)
    result = engine.analyze(PERSON_TEXT + " " + PERSON_TEXT, profile)
    assert result == [_span(0, 10, PERSON, 0.9), _span(12, 22, PERSON, 0.8)]


def test_ner_from_defaults(tmp_path) -> None:
    write_config(
        tmp_path,
        systems={
            "defaults": {"mask_style": "partial", "ner": True},
            "systems": {"checker": {"enabled": True, "pii_types": "all"}},
        },
    )
    config = load_config(tmp_path)
    assert config.profiles()["checker"].ner is True


def test_ner_from_system_overrides_defaults(tmp_path) -> None:
    write_config(
        tmp_path,
        systems={
            "defaults": {"mask_style": "partial", "ner": True},
            "systems": {"checker": {"enabled": True, "pii_types": "all", "ner": False}},
        },
    )
    config = load_config(tmp_path)
    assert config.profiles()["checker"].ner is False


def test_engine_without_ml_works() -> None:
    engine = Engine(_registry(), LabelMasker())
    result = engine.analyze(PERSON_TEXT, PARTIAL_PROFILE)
    assert result == []
