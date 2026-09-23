from __future__ import annotations

import sys

import pytest

from pii_guard.core.normalize import Document
from pii_guard.ml.model import NerEntity, NerUnavailable, TransformersNerModel
from pii_guard.ml.recognizer import NerRecognizer

PERSON = "PERSON"
ADDRESS = "ADDRESS"


class FakeModel:
    def __init__(self, entities: list[NerEntity]) -> None:
        self._entities = entities

    def predict(self, text: str) -> list[NerEntity]:
        return self._entities


def _spans(text: str, entities: list[NerEntity]):
    doc = Document.from_text(text)
    return NerRecognizer(FakeModel(entities)).find(doc)


def test_person_trimmed_to_name() -> None:
    text = "Меня зовут Анна Петрова"
    spans = _spans(text, [NerEntity(0, len(text), PERSON, 0.9)])
    assert len(spans) == 1
    span = spans[0]
    assert span.pii_type == PERSON
    assert text[span.start : span.end] == "Анна Петрова"
    assert span.score >= 0.5


def test_public_figure_no_span() -> None:
    text = "Александр Пушкин написал «Капитанскую дочку»"
    end = text.index("написал") + len("написал")
    spans = _spans(text, [NerEntity(0, end, PERSON, 0.9)])
    assert spans == []


def test_client_public_figure_person() -> None:
    text = "Клиент Пушкин Александр Сергеевич просит карту"
    start = text.index("Пушкин")
    end = text.index("Сергеевич") + len("Сергеевич")
    spans = _spans(text, [NerEntity(start, end, PERSON, 0.9)])
    assert any(span.pii_type == PERSON for span in spans)


def test_courier_no_span() -> None:
    text = "курьер опоздал"
    spans = _spans(text, [NerEntity(0, len("курьер"), PERSON, 0.9)])
    assert spans == []


def test_address_parts() -> None:
    text = "доставка на г. Москва, ул. Ленина 15, кв. 42"
    start = text.index("г.")
    spans = _spans(text, [NerEntity(start, len(text), ADDRESS, 0.9)])
    parts = [text[span.start : span.end] for span in spans]
    assert parts == ["Москва", "Ленина", "15", "42"]
    assert all(span.score >= 0.5 for span in spans)


def test_address_number_continuation() -> None:
    text = "адрес: Екатеринбург, Малышева 36-7"
    start = text.index("Екатеринбург")
    end = text.index("36-") + len("36-")
    spans = _spans(text, [NerEntity(start, end, ADDRESS, 0.94)])
    parts = [text[span.start : span.end] for span in spans]
    assert parts == ["Екатеринбург", "Малышева", "36-7"]


def test_address_phone_excluded() -> None:
    text = "Заказ так и не привезли: Сергей Новиков, 89123456789, ул. Советская 42 кв.17"
    start = text.index("89123456789") + 6
    end = text.index("17") + len("17")
    spans = _spans(text, [NerEntity(start, end, ADDRESS, 0.9)])
    parts = [text[span.start : span.end] for span in spans]
    assert parts == ["Советская", "42", "17"]


def test_bank_branch_no_span() -> None:
    text = "Офис банка находится по адресу ул. Тверская, д. 5"
    start = text.index("ул.")
    spans = _spans(text, [NerEntity(start, len(text), ADDRESS, 0.9)])
    assert spans == []


def test_low_confidence_address() -> None:
    text = "однушка на Ленинском"
    start = text.index("Ленинском")
    spans = _spans(text, [NerEntity(start, start + len("Ленинском"), ADDRESS, 0.9)])
    assert spans and spans[0].score < 0.5


def test_pipeline_merge_and_drop() -> None:
    text = "Иван Иванов и Петр"

    def pipeline(s: str) -> list[dict]:
        return [
            {"entity_group": "PER", "score": 0.9, "start": 0, "end": 4, "word": "Иван"},
            {"entity_group": "PER", "score": 0.8, "start": 5, "end": 11, "word": "Иванов"},
            {"entity_group": "ORG", "score": 0.7, "start": 12, "end": 13, "word": "и"},
            {"entity_group": "PER", "score": 0.6, "start": 14, "end": 18, "word": "Петр"},
        ]

    model = TransformersNerModel("x", pipeline=pipeline)
    result = model.predict(text)
    assert result == [NerEntity(0, 11, PERSON, 0.8), NerEntity(14, 18, PERSON, 0.6)]


def test_pipeline_trims_whitespace() -> None:
    text = "  Иван  "

    def pipeline(s: str) -> list[dict]:
        return [{"entity_group": "PER", "score": 0.9, "start": 0, "end": 9, "word": "  Иван  "}]

    model = TransformersNerModel("x", pipeline=pipeline)
    result = model.predict(text)
    assert result == [NerEntity(2, 6, PERSON, 0.9)]


def test_load_without_torch(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)
    model = TransformersNerModel("some-model")
    with pytest.raises(NerUnavailable):
        model.load()
