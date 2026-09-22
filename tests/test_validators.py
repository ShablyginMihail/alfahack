from pii_guard.recognizers.validators import digits, inn_valid, luhn_valid, snils_valid


def test_digits() -> None:
    assert digits("+7 (916) 123-45-67") == "79161234567"
    assert digits("abc") == ""


def test_luhn_valid_card() -> None:
    assert luhn_valid("4111111111111111") is True


def test_luhn_invalid_card() -> None:
    assert luhn_valid("4111111111111112") is False


def test_luhn_too_short() -> None:
    assert luhn_valid("1") is False


def test_inn_10_valid() -> None:
    assert inn_valid("7707083893") is True


def test_inn_10_invalid() -> None:
    assert inn_valid("7707083894") is False


def test_inn_12_valid() -> None:
    assert inn_valid("500100732259") is True


def test_inn_12_invalid() -> None:
    assert inn_valid("500100732258") is False


def test_inn_wrong_length() -> None:
    assert inn_valid("123") is False


def test_snils_valid() -> None:
    assert snils_valid("11223344595") is True


def test_snils_invalid() -> None:
    assert snils_valid("11223344596") is False


def test_snils_all_same_digits_invalid() -> None:
    assert snils_valid("11111111111") is False
