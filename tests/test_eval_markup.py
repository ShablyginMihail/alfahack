import pytest

from eval.markup import GoldSpan, parse_markup


def test_parse_markup_single() -> None:
    text, spans = parse_markup("Клиент [[PERSON:Иванов Иван Иванович]]")
    assert text == "Клиент Иванов Иван Иванович"
    assert spans == [GoldSpan(7, 27, "PERSON")]


def test_parse_markup_multiple() -> None:
    text, spans = parse_markup(
        "Клиент [[PERSON:Иванов Иван Иванович]], паспорт [[PASSPORT:4509 123456]]"
    )
    assert text == "Клиент Иванов Иван Иванович, паспорт 4509 123456"
    assert spans == [GoldSpan(7, 27, "PERSON"), GoldSpan(37, 48, "PASSPORT")]


def test_parse_markup_cyrillic() -> None:
    text, spans = parse_markup("г. [[ADDRESS:Москва]], ул. [[ADDRESS:Ленина]]")
    assert text == "г. Москва, ул. Ленина"
    assert spans == [GoldSpan(3, 9, "ADDRESS"), GoldSpan(15, 21, "ADDRESS")]


def test_parse_markup_adjacent_spans() -> None:
    text, spans = parse_markup("[[PERSON:Иванов]] [[PASSPORT:4509 123456]]")
    assert text == "Иванов 4509 123456"
    assert spans == [GoldSpan(0, 6, "PERSON"), GoldSpan(7, 18, "PASSPORT")]


def test_parse_markup_no_markup() -> None:
    text, spans = parse_markup("просто текст")
    assert text == "просто текст"
    assert spans == []


def test_parse_markup_broken_no_close() -> None:
    with pytest.raises(ValueError):
        parse_markup("[[PERSON:Иванов")


def test_parse_markup_broken_no_colon() -> None:
    with pytest.raises(ValueError):
        parse_markup("[[PERSON]]")


def test_parse_markup_unknown_type() -> None:
    with pytest.raises(ValueError):
        parse_markup("[[UNKNOWN:value]]")
