from __future__ import annotations

import re

from pii_guard.core.synthetic import SyntheticGenerator
from pii_guard.recognizers.validators import inn_valid, luhn_valid, snils_valid

PERSON_FULL = "Иванов Иван Иванович"
CARDHOLDER_FULL = "IVAN IVANOV"
CARD_16 = "4111 1111 1111 1111"
INN_10 = "7707083893"
INN_12 = "500100732259"
SNILS_TEXT = "112-233-445 95"
DATE_TEXT = "12.05.2015"


def _gen() -> SyntheticGenerator:
    return SyntheticGenerator()


def test_person_format() -> None:
    value = _gen().value("PERSON", PERSON_FULL)
    assert value != PERSON_FULL
    words = value.split()
    assert len(words) == 3
    assert all(w[:1].isupper() and w[1:].islower() for w in words)


def test_person_initials() -> None:
    value = _gen().value("PERSON", "И. И. Иванов")
    assert value != "И. И. Иванов"
    assert re.fullmatch(r"[А-Я]\. ?[А-Я]\. [А-Я][а-я]+", value)


def test_cardholder_format() -> None:
    value = _gen().value("CARDHOLDER", CARDHOLDER_FULL)
    assert value != CARDHOLDER_FULL
    words = value.split()
    assert len(words) == 2
    assert all(w.isupper() for w in words)


def test_email_format() -> None:
    value = _gen().value("EMAIL", "ivanov@mail.ru")
    assert value != "ivanov@mail.ru"
    local, domain = value.split("@")
    assert domain in ("mail.ru", "yandex.ru", "gmail.com", "bk.ru")
    assert any(ch.isdigit() for ch in local)


def test_phone_format() -> None:
    value = _gen().value("PHONE", "+7 (916) 123-45-67")
    assert value != "+7 (916) 123-45-67"
    assert value.startswith("+7 (")
    assert re.fullmatch(r"\+7 \(\d{3}\) \d{3}-\d{2}-\d{2}", value)


def test_card_number_luhn() -> None:
    value = _gen().value("CARD_NUMBER", CARD_16)
    assert value != CARD_16
    assert re.fullmatch(r"\d{4} \d{4} \d{4} \d{4}", value)
    assert luhn_valid("".join(ch for ch in value if ch.isdigit()))


def test_inn_10_valid() -> None:
    value = _gen().value("INN", INN_10)
    assert value != INN_10
    assert value.isdigit() and len(value) == 10
    assert inn_valid(value)


def test_inn_12_valid() -> None:
    value = _gen().value("INN", INN_12)
    assert value != INN_12
    assert value.isdigit() and len(value) == 12
    assert inn_valid(value)


def test_snils_valid() -> None:
    value = _gen().value("SNILS", SNILS_TEXT)
    assert value != SNILS_TEXT
    assert re.fullmatch(r"\d{3}-\d{3}-\d{3} \d{2}", value)
    assert snils_valid("".join(ch for ch in value if ch.isdigit()))


def test_birth_date_format() -> None:
    value = _gen().value("BIRTH_DATE", DATE_TEXT)
    assert value != DATE_TEXT
    assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value)


def test_passport_issue_date_format() -> None:
    value = _gen().value("PASSPORT_ISSUE_DATE", DATE_TEXT)
    assert value != DATE_TEXT
    assert re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", value)


def test_address_city() -> None:
    value = _gen().value("ADDRESS", "Москва", part="city")
    assert value != "Москва"
    assert value[:1].isupper()


def test_address_street() -> None:
    value = _gen().value("ADDRESS", "Ленина", part="street")
    assert value != "Ленина"
    assert value[:1].isupper()


def test_birth_place() -> None:
    value = _gen().value("BIRTH_PLACE", "Москва")
    assert value != "Москва"
    assert value[:1].isupper()


def test_citizenship() -> None:
    value = _gen().value("CITIZENSHIP", "Россия")
    assert value != "Россия"
    assert value in ("Россия", "Беларусь", "Казахстан", "Армения", "Узбекистан")


def test_passport_issuer() -> None:
    value = _gen().value("PASSPORT_ISSUER", "ОУФМС России по г. Москве")
    assert value != "ОУФМС России по г. Москве"
    assert value.startswith("ОУФМС России по г. ")


def test_custom_id_generic() -> None:
    value = _gen().value("CUSTOM_ID", "AB-123456")
    assert value != "AB-123456"
    assert re.fullmatch(r"[A-Z]{2}-\d{6}", value)


def test_deterministic_and_distinct() -> None:
    gen = _gen()
    v1 = gen.value("CARD_NUMBER", CARD_16)
    v2 = gen.value("CARD_NUMBER", CARD_16)
    assert v1 == v2
    v3 = gen.value("CARD_NUMBER", "4222 2222 2222 2222")
    assert v3 != v1


def test_person_deterministic() -> None:
    gen = _gen()
    assert gen.value("PERSON", PERSON_FULL) == gen.value("PERSON", PERSON_FULL)
