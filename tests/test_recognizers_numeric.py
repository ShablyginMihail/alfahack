from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.recognizers.numeric import recognizers
from tests.helpers import PARTIAL_PROFILE


def _engine() -> Engine:
    registry = RecognizerRegistry()
    for recognizer in recognizers():
        registry.register(recognizer)
    return Engine(registry, DefaultMasker(default_type_registry()))


def _mask(text: str) -> str:
    return _engine().mask(text, PARTIAL_PROFILE).text


def _types(text: str) -> set[str]:
    return {span.pii_type for span in _engine().analyze(text, PARTIAL_PROFILE)}


def _luhn(base: str) -> str:
    total = 0
    for i, ch in enumerate(reversed(base)):
        digit = int(ch)
        if (i + 1) % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    check = (10 - total % 10) % 10
    return base + str(check)


def test_email_uppercase() -> None:
    assert _mask("IVANOV@MAIL.RU") == "I*****@MAIL.RU"


def test_email_cyrillic_domain() -> None:
    assert _mask("ivanov@почта.рф") == "i*****@почта.рф"


def test_phone_plus7_parens() -> None:
    assert _mask("+7 (916) 123-45-67") == "+7 (***) ***-**-67"


def test_phone_8_spaces() -> None:
    assert _mask("8 916 123 45 67") == "8 *** *** ** 67"


def test_phone_plus7_compact() -> None:
    assert _mask("+79161234567") == "+7********67"


def test_phone_8_hyphens() -> None:
    assert _mask("8-916-123-45-67") == "8-***-***-**-67"


def test_phone_no_code_with_context() -> None:
    assert _mask("телефон (916) 123-45-67") == "телефон (***) ***-**-67"


def test_phone_no_code_context_word() -> None:
    assert _mask("звоните 916 123 45 67") == "звоните *** *** ** 67"


def test_phone_international() -> None:
    assert _mask("+375 29 123-45-67") == "+375 ** ***-**-67"


def test_card_grouped_spaces() -> None:
    assert _mask("4276 1234 5678 9012") == "4276 **** **** 9012"


def test_card_grouped_hyphens() -> None:
    assert _mask("4276-1234-5678-9012") == "4276-****-****-9012"


def test_card_16_digits_run_valid() -> None:
    assert _mask("4111111111111111") == "4111********1111"


def test_card_valid_luhn_no_context() -> None:
    assert _mask("4111111111111111") == "4111********1111"


def test_card_invalid_with_context() -> None:
    assert _mask("карта 1234567890123456") == "карта 1234********3456"


def test_card_invalid_no_context_no_grouping_not_masked() -> None:
    assert _mask("1234567890123456") == "1234567890123456"


def test_ordinary_numbers_not_masked() -> None:
    assert _mask("заказ 12345") == "заказ 12345"
    assert _mask("2024 год") == "2024 год"
    assert _mask("цена 1500 рублей") == "цена 1500 рублей"


def test_card_next_to_phone_each_masked_by_type() -> None:
    text = "карта 4276 1234 5678 9012, телефон +7 916 123 45 67"
    assert _mask(text) == "карта 4276 **** **** 9012, телефон +7 *** *** ** 67"


def test_card_13_digits_ogrn_not_masked() -> None:
    number = _luhn("123456789012")
    assert _mask(f"ОГРН {number}") == f"ОГРН {number}"


def test_card_13_digits_valid_masked() -> None:
    number = _luhn("123456789012")
    assert _mask(number) != number


def test_inn_with_label() -> None:
    assert _mask("ИНН 7707083893") == "ИНН 77******93"


def test_inn_12_digits_with_label() -> None:
    assert _mask("инн: 500100732259") == "инн: 50********59"


def test_inn_separated_masked() -> None:
    assert _mask("ИНН 7707 083 893") != "ИНН 7707 083 893"


def test_inn_without_label_not_masked() -> None:
    assert _mask("номер 7707083893") == "номер 7707083893"


def test_cvv_short() -> None:
    assert _mask("CVV 123") == "CVV ***"


def test_cvc2() -> None:
    assert _mask("cvc2: 4567") == "cvc2: ****"


def test_cvv_code_security() -> None:
    assert _mask("код безопасности 321") == "код безопасности ***"


def test_pin_short() -> None:
    assert _mask("ПИН 1234") == "ПИН ****"


def test_pin_code_hyphen() -> None:
    assert _mask("pin-код: 9876") == "pin-код: ****"


def test_pin_code_word() -> None:
    assert _mask("пинкод 123456") == "пинкод ******"


def test_card_and_cvv_each_masked_by_type() -> None:
    text = "карта 4276 1234 5678 9012, cvv 123"
    assert _mask(text) == "карта 4276 **** **** 9012, cvv ***"


def test_card_groups_not_pin() -> None:
    text = "пин-код от карты 4276 1234 5678 9012"
    assert _mask(text) == "пин-код от карты 4276 **** **** 9012"


def test_cvv_case_insensitive() -> None:
    assert _mask("CVV 123") == "CVV ***"
    assert _mask("Cvv 123") == "Cvv ***"


def test_pin_case_insensitive() -> None:
    assert _mask("ПИН 1234") == "ПИН ****"
    assert _mask("Пин 1234") == "Пин ****"


def test_inn_separated_not_phone() -> None:
    text = "ИНН 5758622243, ТЕЛЕФОН 901 890 88 71"
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    phone = [s for s in spans if s.pii_type == "PHONE"]
    inn = [s for s in spans if s.pii_type == "INN"]
    assert phone and inn
    assert text[phone[0].start : phone[0].end] == "901 890 88 71"
    assert text[inn[0].start : inn[0].end] == "5758622243"


def _span_at(text: str, value: str, pii_type: str) -> None:
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    start = text.index(value)
    end = start + len(value)
    matching = [s for s in spans if s.pii_type == pii_type and s.start == start and s.end == end]
    assert matching, f"no {pii_type} span at {value!r} in {text!r}"


def test_pin_after_card_number() -> None:
    text = "ПИН-код от карты 4276 3801 2345 6789 — 4321"
    _span_at(text, "4321", "PIN")


def test_pin_context_after_value() -> None:
    text = "4321 — это ПИН"
    _span_at(text, "4321", "PIN")


def test_phone_no_code_with_label() -> None:
    text = "ТЕЛЕФОН 942 561 81 85, КОД ПОДРАЗДЕЛЕНИЯ 195-542"
    _span_at(text, "942 561 81 85", "PHONE")


def test_cvv_on_back() -> None:
    assert "CVV" in _types("код на обороте карты 456")


def test_card_16_digits_run_no_context() -> None:
    assert "CARD_NUMBER" in _types("Переведите на 4276380012345678")
    assert "CARD_NUMBER" not in _types("Номер договора 4276380012345678")
