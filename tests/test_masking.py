from __future__ import annotations

import string

from hypothesis import given, settings
from hypothesis import strategies as st

from pii_guard.core.demasking import replace_masked_fragments, restore, unmask
from pii_guard.core.masking import (
    DEFAULT_PARTIAL_SPECS,
    DefaultMasker,
    PartialSpec,
    mask_email,
    mask_initials,
    mask_partial,
    mask_phone,
)
from pii_guard.core.models import MappingRecord, Span
from pii_guard.core.policy import Profile
from pii_guard.core.types import default_type_registry

CLIENT_PASSPORT_TEXT = "Клиент Иванов Иван Иванович, паспорт 4509 123456"
IVANOV = "Иванов Иван"
PETROV = "Петров Пётр"
PHONE_PARENS = "+7 (916) 123-45-67"
IVANOV_FULL = "Иванов Иван Иванович"
PHONE_PLAIN = "+7 916 123-45-67"


def _span(start: int, end: int, pii_type: str) -> Span:
    return Span(start=start, end=end, pii_type=pii_type, score=1.0, recognizer="test")


def _span_at(text: str, fragment: str, pii_type: str) -> Span:
    start = text.index(fragment)
    return _span(start, start + len(fragment), pii_type)


def _masker() -> DefaultMasker:
    return DefaultMasker(default_type_registry())


def test_mask_partial_contract_example() -> None:
    assert mask_partial("4509 123456", PartialSpec(2, 2)) == "45** ****56"


def test_mask_partial_phone() -> None:
    assert mask_partial(PHONE_PARENS, PartialSpec(1, 2)) == "+7 (***) ***-**-67"


def test_mask_partial_card() -> None:
    assert mask_partial("4276 1234 5678 9012", PartialSpec(4, 4)) == "4276 **** **** 9012"


def test_mask_partial_all_masked() -> None:
    assert mask_partial("123", PartialSpec(0, 0)) == "***"


def test_mask_partial_keeps_separators_when_all_masked() -> None:
    assert mask_partial("12-3", PartialSpec(2, 2)) == "**-*"


def test_mask_initials_full_name() -> None:
    assert mask_initials(IVANOV_FULL) == "И. И. И."


def test_mask_initials_abbreviated() -> None:
    assert mask_initials("иванов и.и.") == "И. И. И."


def test_mask_initials_latin() -> None:
    assert mask_initials("IVAN PETROV") == "I. P."


def test_mask_initials_hyphenated_word() -> None:
    assert mask_initials("Салтыков-Щедрин") == "С."


def test_mask_email() -> None:
    assert mask_email("ivanov@mail.ru") == "i*****@mail.ru"


def test_mask_phone_plus7_parens() -> None:
    assert mask_phone(PHONE_PARENS) == "+7 (***) ***-**-67"


def test_mask_phone_8_spaces() -> None:
    assert mask_phone("8 916 123 45 67") == "8 *** *** ** 67"


def test_mask_phone_plus7_compact() -> None:
    assert mask_phone("+79161234567") == "+7********67"


def test_mask_phone_8_hyphens() -> None:
    assert mask_phone("8-916-123-45-67") == "8-***-***-**-67"


def test_mask_phone_no_code_parens() -> None:
    assert mask_phone("(916) 123-45-67") == "(***) ***-**-67"


def test_mask_phone_no_code_spaces() -> None:
    assert mask_phone("916 123 45 67") == "*** *** ** 67"


def test_mask_phone_international_spaces() -> None:
    assert mask_phone("+375 29 123-45-67") == "+375 ** ***-**-67"


def test_mask_phone_international_compact() -> None:
    assert mask_phone("+375291234567") == "+375*******67"


def test_default_partial_specs() -> None:
    assert DEFAULT_PARTIAL_SPECS["PASSPORT"] == PartialSpec(2, 2)
    assert DEFAULT_PARTIAL_SPECS["CARD_NUMBER"] == PartialSpec(4, 4)
    assert DEFAULT_PARTIAL_SPECS["PHONE"] == PartialSpec(1, 2)
    assert DEFAULT_PARTIAL_SPECS["INN"] == PartialSpec(2, 2)
    assert DEFAULT_PARTIAL_SPECS["DRIVER_LICENSE"] == PartialSpec(2, 2)
    assert DEFAULT_PARTIAL_SPECS["FOREIGN_PASSPORT"] == PartialSpec(2, 2)
    assert DEFAULT_PARTIAL_SPECS["SNILS"] == PartialSpec(0, 2)


def test_partial_style_uses_default_specs() -> None:
    text = CLIENT_PASSPORT_TEXT
    spans = [
        _span_at(text, IVANOV_FULL, "PERSON"),
        _span_at(text, "4509 123456", "PASSPORT"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="partial"))
    assert result.text == "Клиент И. И. И., паспорт 45** ****56"


def test_partial_style_custom_spec_overrides_default() -> None:
    masker = DefaultMasker(default_type_registry(), partial_specs={"PASSPORT": PartialSpec(0, 0)})
    text = "паспорт 4509 123456"
    spans = [_span_at(text, "4509 123456", "PASSPORT")]
    result = masker.apply(text, spans, Profile(name="checker", mask_style="partial"))
    assert result.text == "паспорт **** ******"


def test_label_style() -> None:
    text = CLIENT_PASSPORT_TEXT
    spans = [
        _span_at(text, IVANOV_FULL, "PERSON"),
        _span_at(text, "4509 123456", "PASSPORT"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="label"))
    assert result.text == "Клиент [ФИО], паспорт [ПАСПОРТ]"


def test_full_style_masks_every_char() -> None:
    cases = [
        (IVANOV_FULL, "PERSON"),
        ("ivanov@mail.ru", "EMAIL"),
        (PHONE_PARENS, "PHONE"),
        ("4509 123456", "PASSPORT"),
        ("г. Москва, ул. Ленина, д. 5", "ADDRESS"),
    ]
    for value, pii_type in cases:
        text = f"данные {value} конец"
        spans = [_span_at(text, value, pii_type)]
        result = _masker().apply(text, spans, Profile(name="checker", mask_style="full"))
        expected = f"данные {'*' * len(value)} конец"
        assert result.text == expected
        assert len(result.replacements[0].masked) == len(value)
        assert not any(ch.isalnum() for ch in result.replacements[0].masked)


def test_token_style_repeated_value_same_number() -> None:
    text = "Иванов Иван и ИВАНОВ ИВАН"
    spans = [
        _span_at(text, IVANOV, "PERSON"),
        _span_at(text, "ИВАНОВ ИВАН", "PERSON"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="token"))
    assert result.text == "[ФИО_1] и [ФИО_1]"


def test_token_style_distinct_values_distinct_numbers() -> None:
    text = "Иванов Иван и Петров Пётр"
    spans = [
        _span_at(text, IVANOV, "PERSON"),
        _span_at(text, PETROV, "PERSON"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="token"))
    assert result.text == "[ФИО_1] и [ФИО_2]"


def test_token_style_normalized_phone_same_token() -> None:
    text = "+7 916 123-45-67 и +79161234567"
    spans = [
        _span_at(text, PHONE_PLAIN, "PHONE"),
        _span_at(text, "+79161234567", "PHONE"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="token"))
    assert result.text == "[ТЕЛЕФОН_1] и [ТЕЛЕФОН_1]"


def test_token_style_types_numbered_independently() -> None:
    text = "Иванов Иван, 4509 123456, Петров Пётр"
    spans = [
        _span_at(text, IVANOV, "PERSON"),
        _span_at(text, "4509 123456", "PASSPORT"),
        _span_at(text, PETROV, "PERSON"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="token"))
    assert result.text == "[ФИО_1], [ПАСПОРТ_1], [ФИО_2]"


def test_unknown_mask_style_raises() -> None:
    import pytest

    text = IVANOV
    spans = [_span_at(text, IVANOV, "PERSON")]
    masker = _masker()
    profile = Profile(name="checker", mask_style="bogus")
    with pytest.raises(ValueError):
        masker.apply(text, spans, profile)


def test_unmask_roundtrip_partial() -> None:
    text = CLIENT_PASSPORT_TEXT
    spans = [
        _span_at(text, IVANOV_FULL, "PERSON"),
        _span_at(text, "4509 123456", "PASSPORT"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="partial"))
    record = MappingRecord("fp", result.text, result.replacements)
    assert unmask(result.text, record) == text


def test_unmask_roundtrip_label() -> None:
    text = CLIENT_PASSPORT_TEXT
    spans = [
        _span_at(text, IVANOV_FULL, "PERSON"),
        _span_at(text, "4509 123456", "PASSPORT"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="label"))
    record = MappingRecord("fp", result.text, result.replacements)
    assert unmask(result.text, record) == text


def test_unmask_roundtrip_token() -> None:
    text = "Иванов Иван и Петров Пётр, 4509 123456"
    spans = [
        _span_at(text, IVANOV, "PERSON"),
        _span_at(text, PETROV, "PERSON"),
        _span_at(text, "4509 123456", "PASSPORT"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="token"))
    record = MappingRecord("fp", result.text, result.replacements)
    assert unmask(result.text, record) == text


@st.composite
def _text_and_spans(draw: st.DrawFn) -> tuple[str, tuple[Span, ...]]:
    alphabet = st.text(
        alphabet=string.ascii_letters + string.digits + " +-()@.", min_size=1, max_size=4
    )
    pieces = draw(st.lists(alphabet, min_size=1, max_size=8))
    text = "".join(pieces)

    types = ["PERSON", "PASSPORT", "EMAIL", "PHONE"]
    spans: list[Span] = []
    cursor = 0
    for piece in pieces:
        if draw(st.booleans()) and piece:
            spans.append(_span(cursor, cursor + len(piece), draw(st.sampled_from(types))))
        cursor += len(piece)
    return text, tuple(spans)


@given(_text_and_spans())
@settings(max_examples=200)
def test_restore_roundtrip_partial(data: tuple[str, tuple[Span, ...]]) -> None:
    text, spans = data
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="partial"))
    assert restore(result.text, result.replacements) == text


@given(_text_and_spans())
@settings(max_examples=200)
def test_restore_roundtrip_label(data: tuple[str, tuple[Span, ...]]) -> None:
    text, spans = data
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="label"))
    assert restore(result.text, result.replacements) == text


@given(_text_and_spans())
@settings(max_examples=200)
def test_restore_roundtrip_token(data: tuple[str, tuple[Span, ...]]) -> None:
    text, spans = data
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="token"))
    assert restore(result.text, result.replacements) == text


SYNTHETIC_TEXT = "Клиент Иванов Иван Иванович, телефон +7 916 123-45-67, карта 4276 3801 2345 6789"


def _synthetic_spans(text: str) -> list[Span]:
    return [
        _span_at(text, IVANOV_FULL, "PERSON"),
        _span_at(text, PHONE_PLAIN, "PHONE"),
        _span_at(text, "4276 3801 2345 6789", "CARD_NUMBER"),
    ]


def test_synthetic_style_replaces_values() -> None:
    result = _masker().apply(
        SYNTHETIC_TEXT,
        _synthetic_spans(SYNTHETIC_TEXT),
        Profile(name="checker", mask_style="synthetic"),
    )
    assert IVANOV_FULL not in result.text
    assert PHONE_PLAIN not in result.text
    assert "4276 3801 2345 6789" not in result.text
    assert {r.pii_type for r in result.replacements} == {"PERSON", "PHONE", "CARD_NUMBER"}
    for r in result.replacements:
        assert r.masked != r.original


def test_synthetic_unmask_roundtrip() -> None:
    result = _masker().apply(
        SYNTHETIC_TEXT,
        _synthetic_spans(SYNTHETIC_TEXT),
        Profile(name="checker", mask_style="synthetic"),
    )
    record = MappingRecord("fp", result.text, result.replacements)
    assert unmask(result.text, record) == SYNTHETIC_TEXT


def test_synthetic_replace_masked_fragments() -> None:
    text = "Клиент Иванов Иван Иванович, телефон +7 916 123-45-67"
    spans = [
        _span_at(text, IVANOV_FULL, "PERSON"),
        _span_at(text, PHONE_PLAIN, "PHONE"),
    ]
    result = _masker().apply(text, spans, Profile(name="checker", mask_style="synthetic"))
    person_masked = next(r.masked for r in result.replacements if r.pii_type == "PERSON")
    phone_masked = next(r.masked for r in result.replacements if r.pii_type == "PHONE")
    modified = f"Звонил {phone_masked} по вопросу, представился {person_masked}"
    restored = replace_masked_fragments(modified, result.replacements)
    assert IVANOV_FULL in restored
    assert PHONE_PLAIN in restored
