from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pii_guard.core.demasking import replace_masked_fragments, restore, unmask
from pii_guard.core.models import MappingRecord, Replacement


def _replacement(
    start: int,
    end: int,
    masked_start: int,
    original: str,
    masked: str,
    pii_type: str = "PHONE",
) -> Replacement:
    return Replacement(
        start=start,
        end=end,
        masked_start=masked_start,
        original=original,
        masked=masked,
        pii_type=pii_type,
    )


def test_restore_multiple_replacements_varying_length() -> None:
    text = "Звоните 45** ****56, карта 1234 **** **** 5678"
    phone_mask = "45** ****56"
    card_mask = "1234 **** **** 5678"
    phone_start = text.index(phone_mask)
    card_start = text.index(card_mask)
    replacements = [
        _replacement(8, 18, phone_start, "4509 123456", phone_mask, "PHONE"),
        _replacement(26, 46, card_start, "1234 5678 9012 3456", card_mask, "CARD_NUMBER"),
    ]
    assert restore(text, replacements) == "Звоните 4509 123456, карта 1234 5678 9012 3456"


def test_restore_mask_shorter_than_original() -> None:
    text = "ИНН 77** **** **"
    replacements = [_replacement(4, 16, 4, "7707083893", "77** **** **", "INN")]
    assert restore(text, replacements) == "ИНН 7707083893"


def test_restore_mask_longer_than_original() -> None:
    text = "ПИН ******"
    replacements = [_replacement(4, 7, 4, "123", "******", "PIN")]
    assert restore(text, replacements) == "ПИН 123"


def test_restore_empty_masked_inserts_original() -> None:
    masked_text = "ИНН "
    replacements = [_replacement(4, 16, 4, "7707083893", "", "INN")]
    assert restore(masked_text, replacements) == "ИНН 7707083893"


def test_restore_returns_none_when_text_changed() -> None:
    text = "Звоните 45** ***56 пожалуйста"
    replacements = [_replacement(8, 18, 8, "4509 123456", "45** ****56", "PHONE")]
    assert restore(text, replacements) is None


def test_restore_returns_none_on_overlapping_replacements() -> None:
    text = "abcdef"
    replacements = [
        _replacement(0, 3, 0, "ABC", "abc", "PHONE"),
        _replacement(2, 5, 2, "DEF", "cde", "PHONE"),
    ]
    assert restore(text, replacements) is None


def test_replace_masked_fragments_inserts_originals_into_modified_text() -> None:
    text = "Ваш номер 45** ****56 был изменён, перезвоните на 45** ****56"
    replacements = [_replacement(10, 20, 10, "4509 123456", "45** ****56", "PHONE")]
    assert (
        replace_masked_fragments(text, replacements)
        == "Ваш номер 4509 123456 был изменён, перезвоните на 4509 123456"
    )


def test_replace_masked_fragments_repeated_masked_with_different_originals() -> None:
    text = "45** ****56 и 45** ****56"
    replacements = [
        _replacement(0, 10, 0, "4509 123456", "45** ****56", "PHONE"),
        _replacement(14, 24, 14, "7999 000000", "45** ****56", "PHONE"),
    ]
    assert replace_masked_fragments(text, replacements) == "4509 123456 и 7999 000000"


def test_replace_masked_fragments_after_exhaustion_uses_last() -> None:
    text = "45** ****56 45** ****56 45** ****56"
    replacements = [
        _replacement(0, 10, 0, "4509 123456", "45** ****56", "PHONE"),
        _replacement(11, 21, 11, "7999 000000", "45** ****56", "PHONE"),
    ]
    assert replace_masked_fragments(text, replacements) == "4509 123456 7999 000000 7999 000000"


def test_unmask_exact_text_restores() -> None:
    record = MappingRecord(
        original_fp="fp",
        masked_text="ИНН 77** **** **",
        replacements=(_replacement(4, 16, 4, "7707083893", "77** **** **", "INN"),),
    )
    assert unmask(record.masked_text, record) == "ИНН 7707083893"


def test_unmask_modified_text_replaces_fragments() -> None:
    record = MappingRecord(
        original_fp="fp",
        masked_text="ИНН 77** **** **",
        replacements=(_replacement(4, 16, 4, "7707083893", "77** **** **", "INN"),),
    )
    assert unmask("ИНН 77** **** ** указан в заявке", record) == "ИНН 7707083893 указан в заявке"


@st.composite
def _text_and_replacements(draw: st.DrawFn) -> tuple[str, tuple[Replacement, ...], str]:
    alphabet = st.text(alphabet="abc XYZ012", min_size=1, max_size=4)
    pieces = draw(st.lists(alphabet, min_size=1, max_size=6))
    text = "".join(pieces)

    replacements: list[Replacement] = []
    masked_parts: list[str] = []
    cursor = 0
    for piece in pieces:
        if draw(st.booleans()) and piece:
            masked = draw(st.text(alphabet="*#", min_size=1, max_size=len(piece) + 2))
            replacements.append(
                _replacement(cursor, cursor + len(piece), len("".join(masked_parts)), piece, masked)
            )
            masked_parts.append(masked)
        else:
            masked_parts.append(piece)
        cursor += len(piece)
    return text, tuple(replacements), "".join(masked_parts)


@given(_text_and_replacements())
@settings(max_examples=200)
def test_unmask_roundtrip(data: tuple[str, tuple[Replacement, ...], str]) -> None:
    text, replacements, masked_text = data
    record = MappingRecord(
        original_fp="fp",
        masked_text=masked_text,
        replacements=replacements,
    )
    assert unmask(masked_text, record) == text
