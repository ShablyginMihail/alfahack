from __future__ import annotations

from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.normalize import Document
from pii_guard.core.policy import Profile
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.recognizers.standalone import StandaloneValueRecognizer

FULL_PROFILE = Profile(name="checker", mask_style="full")

VALUES = [
    "Иванов",
    "Анна",
    "12.03.1985",
    "12/03/1985",
    "03.12.85",
    "12 марта 1985 года",
    "4509 123456",
    "4509123456",
    "770-001",
    "500100732259",
    "4276380123456789",
    "99 12 345678",
    "123",
    "1234",
    "Москва",
    "г. Саратов",
    "Россия",
    "Российская Федерация",
    "ОУФМС России по г. Москве",
    "ГУ МВД России по Московской области",
]

EXCEPTIONS = [
    "Обсудили условия вклада",
    "привет",
    "12",
    "Москва — столица России",
    "Иванов пришёл в отделение",
    "Паспорт 4509 123456 выдан",
    "Отделение банка находится по адресу: г. Москва, ул. Тверская, д. 10",
    "Отдел кадров",
]


def _engine() -> Engine:
    registry = RecognizerRegistry()
    registry.register(StandaloneValueRecognizer())
    return Engine(registry, DefaultMasker(default_type_registry()))


def _masked(text: str) -> str:
    return _engine().mask(text, FULL_PROFILE).text


def test_standalone_values_found_and_masked() -> None:
    recognizer = StandaloneValueRecognizer()
    for value in VALUES:
        doc = Document.from_text(value)
        spans = [s for s in recognizer.find(doc)]
        assert spans, value
        span = spans[0]
        masked = _masked(value)
        masked_span = masked[span.start : span.end]
        assert not any(ch.isalnum() for ch in masked_span), value


def test_standalone_marker_and_tail_kept() -> None:
    recognizer = StandaloneValueRecognizer()
    doc = Document.from_text("г. Саратов")
    span = next(iter(recognizer.find(doc)))
    assert doc.text[span.start : span.end] == "Саратов"
    assert "г." in _masked("г. Саратов")

    doc2 = Document.from_text("12 марта 1985 года")
    span2 = next(iter(recognizer.find(doc2)))
    assert doc2.text[span2.start : span2.end] == "12 марта 1985"
    assert "года" in _masked("12 марта 1985 года")


def test_standalone_whitespace_stripped() -> None:
    recognizer = StandaloneValueRecognizer()
    doc = Document.from_text("  4509 123456  ")
    spans = [s for s in recognizer.find(doc)]
    assert spans
    span = spans[0]
    assert doc.text[span.start : span.end] == "4509 123456"


def test_standalone_exceptions_not_found() -> None:
    recognizer = StandaloneValueRecognizer()
    for value in EXCEPTIONS:
        doc = Document.from_text(value)
        spans = [s for s in recognizer.find(doc)]
        assert not spans, value


def test_standalone_long_issuer() -> None:
    text = "ТП № 2 ОУФМС России по Санкт-Петербургу и Ленинградской обл. в Приморском р-не"
    recognizer = StandaloneValueRecognizer()
    doc = Document.from_text(text)
    spans = [s for s in recognizer.find(doc)]
    assert spans
    span = spans[0]
    assert span.pii_type == "PASSPORT_ISSUER"
    assert doc.text[span.start : span.end] == text
