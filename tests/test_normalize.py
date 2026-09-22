from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pii_guard.core.normalize import Document, normalize


def test_length_preserved_on_mixed_strings() -> None:
    samples = [
        "ИВАНОВ Ёжик — ТЕСТ",
        "İstanbul",
        "Привет\u00a0мир\u200bтест",
        "«кавычки» и 'апострофы'",
        "дефис‐тире–длинное—",
        "😀 эмодзи и текст",
        "ЁЖИК ёжик ЁЖ",
    ]
    for text in samples:
        assert len(normalize(text)) == len(text)


def test_known_transformation() -> None:
    assert normalize("ИВАНОВ Ёжик — ТЕСТ") == "иванов ежик - тест"


def test_yo_to_e() -> None:
    assert normalize("ЁЖИК ёжик") == "ежик ежик"


def test_dashes_to_hyphen() -> None:
    assert normalize("а‐б‑в‒г–д—е―ж−з⁃и﹣й－к") == "а-б-в-г-д-е-ж-з-и-й-к"


def test_spaces_normalized() -> None:
    assert normalize("а\u00a0б\u2003в\u3000г") == "а б в г"


def test_zero_width_to_space() -> None:
    assert normalize("а\u200bб\u200cв\u200dг\u2060д\ufeffе") == "а б в г д е"


def test_quotes_and_apostrophes() -> None:
    assert normalize("«а» „б“ “в” ”г” ‟д” ″е″") == '"а" "б" "в" "г" "д" "е"'
    assert normalize("‘а’ ‚б‚ ‛в‛ ′г′") == "'а' 'б' 'в' 'г'"


def test_dotted_i_kept() -> None:
    assert normalize("İ") == "İ"


def test_document_from_text() -> None:
    doc = Document.from_text("ИВАНОВ Ёжик — ТЕСТ")
    assert doc.text == "ИВАНОВ Ёжик — ТЕСТ"
    assert doc.norm == "иванов ежик - тест"


@given(st.text())
@settings(max_examples=200)
def test_length_preserved_for_arbitrary_text(text: str) -> None:
    assert len(normalize(text)) == len(text)
