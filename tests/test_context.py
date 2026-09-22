from __future__ import annotations

from pii_guard.core.context import compile_keywords, find_keyword, has_keyword
from pii_guard.core.normalize import Document


def _doc(text: str) -> Document:
    return Document.from_text(text)


def test_prefix_match_across_cases() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("серия паспорта 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) is not None


def test_prefix_match_derived_word() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("паспортные данные 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) is not None


def test_word_boundary_does_not_match_compound() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("загранпаспорт 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) is None


def test_uppercase_matches() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("ПАСПОРТ 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) is not None


def test_window_before() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("паспорт " + "x" * 50 + " 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern, window=40) is None
    assert find_keyword(doc, start, start + 4, pattern, window=60) is not None


def test_direction_after() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("1234 паспорт")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern, direction="after") is not None
    assert find_keyword(doc, start, start + 4, pattern, direction="before") is None


def test_direction_both() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("паспорт 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern, direction="both") is not None


def test_distance_before() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("паспорт 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) == 8


def test_distance_after() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("1234 паспорт")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern, direction="after") == 1


def test_distance_both_takes_nearest() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("паспорт 1234 паспорт")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern, direction="both") == 1


def test_has_keyword_wrapper() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("паспорт 1234")
    start = doc.norm.index("1234")
    assert has_keyword(doc, start, start + 4, pattern) is True
    assert has_keyword(doc, start, start + 4, pattern, direction="after") is False


def test_long_words_first_in_alternative() -> None:
    pattern = compile_keywords(["паспорт", "загранпаспорт"])
    doc = _doc("загранпаспорт 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) is not None


def test_no_keyword_returns_none() -> None:
    pattern = compile_keywords(["паспорт"])
    doc = _doc("просто текст 1234")
    start = doc.norm.index("1234")
    assert find_keyword(doc, start, start + 4, pattern) is None
