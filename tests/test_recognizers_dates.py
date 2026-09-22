from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.policy import CHECKER_PROFILE, Profile
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.settings import Settings


def _engine() -> Engine:
    registry = RecognizerRegistry.from_modules(Settings().recognizer_modules)
    return Engine(registry, DefaultMasker(default_type_registry()))


def _mask(text: str) -> str:
    return _engine().mask(text, CHECKER_PROFILE).text


def _types(text: str) -> set[str]:
    return {span.pii_type for span in _engine().analyze(text, CHECKER_PROFILE)}


def test_birth_date_numeric() -> None:
    assert _mask("дата рождения 12.03.1985") == "дата рождения **.**.****"


def test_birth_date_slash() -> None:
    assert _mask("родился 03/12/1985") == "родился **/**/****"


def test_birth_date_iso() -> None:
    assert _mask("д.р. 1985-03-12") == "д.р. ****-**-**"


def test_birth_date_context_after() -> None:
    assert "BIRTH_DATE" in _types("1985-03-12 день рождения")


def test_words_date_without_goda() -> None:
    assert "BIRTH_DATE" in _types(
        "Родился тринадцатого сентября тысяча девятьсот восемьдесят пятого"
    )


def test_words_date_issue_without_goda() -> None:
    assert "PASSPORT_ISSUE_DATE" in _types(
        "паспорт выдан девятого января тысяча девятьсот восемьдесят пятого"
    )


def test_birth_date_gr_after() -> None:
    assert _mask("г.р. 1985.12.03") == "г.р. ****.**.**"


def test_birth_date_two_digit_year() -> None:
    assert _mask("дата рождения 12.03.85") == "дата рождения **.**.**"


def test_birth_date_month_word() -> None:
    assert _mask("родилась 12 марта 1985 года") == "родилась ** ***** **** года"


def test_birth_date_month_year() -> None:
    assert _mask("родился в марте 1985") == "родился в ***** ****"


def test_birth_date_words() -> None:
    text = "дата рождения: двенадцатого марта тысяча девятьсот восемьдесят пятого года"
    result = _mask(text)
    assert result.endswith(" года")
    assert "двенадцатого" not in result


def test_birth_date_words_two_thousand() -> None:
    text = "дата рождения: первое января двухтысячного года"
    result = _mask(text)
    assert result.endswith(" года")
    assert "января" not in result


def test_birth_date_words_two_thousand_five() -> None:
    text = "родился пятого мая две тысячи пятого года"
    result = _mask(text)
    assert result.endswith(" года")
    assert "мая" not in result


def test_birth_date_words_ninety() -> None:
    text = "дата рождения: третьего июня тысяча девятьсот девяностого года"
    result = _mask(text)
    assert result.endswith(" года")
    assert "июня" not in result


def test_birth_date_year_words_only() -> None:
    text = "родился в тысяча девятьсот восемьдесят пятом году"
    result = _mask(text)
    assert result.endswith(" году")
    assert "восемьдесят" not in result


def test_passport_issue_date() -> None:
    assert _mask("паспорт выдан 01.02.2010") == "паспорт выдан **.**.****"


def test_passport_issue_date_month_word() -> None:
    assert _mask("дата выдачи 5 мая 2015 г.") == "дата выдачи * *** **** г."


def test_no_context_recent_date_not_masked() -> None:
    assert _mask("встреча 12.03.2024") == "встреча 12.03.2024"


def test_no_context_old_date_not_masked_normal() -> None:
    assert _mask("12.03.1985") == "12.03.1985"


def test_no_context_old_date_masked_strict() -> None:
    strict = Profile(name="s", strict=True)
    result = _engine().mask("12.03.1985", strict).text
    assert result != "12.03.1985"


def test_impossible_dates_not_masked() -> None:
    assert _mask("31.02.2020") == "31.02.2020"
    assert _mask("12.13.2020") == "12.13.2020"


def test_version_and_time_not_masked() -> None:
    assert _mask("версия 1.2.3") == "версия 1.2.3"
    assert _mask("14:30") == "14:30"


def test_case_insensitive() -> None:
    assert _mask("ДАТА РОЖДЕНИЯ 12 МАРТА 1985") == "ДАТА РОЖДЕНИЯ ** ***** ****"


def test_birth_date_type() -> None:
    assert "BIRTH_DATE" in _types("дата рождения 12.03.1985")


def test_passport_issue_date_type() -> None:
    assert "PASSPORT_ISSUE_DATE" in _types("паспорт выдан 01.02.2010")
