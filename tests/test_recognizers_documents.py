from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.settings import Settings
from tests.helpers import PARTIAL_PROFILE


def _engine() -> Engine:
    registry = RecognizerRegistry.from_modules(Settings().recognizer_modules)
    return Engine(registry, DefaultMasker(default_type_registry()))


def _mask(text: str) -> str:
    return _engine().mask(text, PARTIAL_PROFILE).text


def _types(text: str) -> set[str]:
    return {span.pii_type for span in _engine().analyze(text, PARTIAL_PROFILE)}


def _snils(base9: str) -> str:
    total = sum(int(ch) * (9 - i) for i, ch in enumerate(base9))
    if total > 101:
        total %= 101
    if total in (100, 101):
        total = 0
    return base9 + f"{total:02d}"


def test_passport_masked() -> None:
    text = "Клиент Иванов Иван Иванович, паспорт 4509 123456"
    assert _mask(text) == "Клиент И. И. И., паспорт 45** ****56"


def test_passport_separate() -> None:
    assert _mask("серия 4509 номер 123456") == "серия 45** номер ****56"


def test_passport_separate_with_no() -> None:
    assert _mask("паспорт серии 45 09 № 123456") != "паспорт серии 45 09 № 123456"


def test_passport_no_context_not_masked() -> None:
    assert _mask("Заказ 4509 123456 доставлен") == "Заказ 4509 123456 доставлен"


def test_division_code() -> None:
    assert _mask("код подразделения 770-001") == "код подразделения ***-***"


def test_division_code_no_context_not_masked() -> None:
    assert _mask("Артикул 770-001 есть на складе") == "Артикул 770-001 есть на складе"


def test_driver_license_type() -> None:
    assert "DRIVER_LICENSE" in _types("водительское удостоверение 99 12 345678")


def test_driver_old_format_masked() -> None:
    assert _mask("ВУ 77 АВ 123456") != "ВУ 77 АВ 123456"


def test_passport_99_12_type() -> None:
    assert "PASSPORT" in _types("паспорт 99 12 345678")


def test_snils_masked() -> None:
    assert _mask("СНИЛС 112-233-445 95") != "СНИЛС 112-233-445 95"


def test_snils_11_digits_with_context() -> None:
    number = _snils("112233445")
    assert "SNILS" in _types(f"СНИЛС {number}")
    assert "PHONE" not in _types(f"СНИЛС {number}")


def test_foreign_passport() -> None:
    assert "FOREIGN_PASSPORT" in _types("загранпаспорт 75 1234567")


def test_case_insensitive() -> None:
    assert _mask("ПАСПОРТ 4509 123456") == "ПАСПОРТ 45** ****56"
    assert _mask("Серия 4509 номер 123456") == "Серия 45** номер ****56"
    assert _mask("СНИЛС 112-233-445 95") != "СНИЛС 112-233-445 95"


def test_year_after_passport_not_masked() -> None:
    text = "Паспорт 4509 123456 выдан 12.05.2015"
    assert _mask(text) == "Паспорт 45** ****56 выдан **.**.****"


def test_year_with_passport_not_masked() -> None:
    assert _mask("Паспорт получен в 2015 году") == "Паспорт получен в 2015 году"


def test_working_hours_not_masked() -> None:
    assert (
        _mask("Паспортный стол работает с 0900 до 1800")
        == "Паспортный стол работает с 0900 до 1800"
    )


def test_year_after_driver_license_not_masked() -> None:
    text = "Водительские права 77 АВ 123456, выданы в 2019"
    assert _mask(text) == "Водительские права 77 ** ****56, выданы в 2019"


def test_application_number_with_passport_not_masked() -> None:
    assert _mask("номер заявки 123456 паспорт") == "номер заявки 123456 паспорт"


def test_passport_separate_with_labels() -> None:
    assert _mask("Серия паспорта: 45 09, номер: 123456") == "Серия паспорта: 45 **, номер: ****56"


def test_passport_separate_plain() -> None:
    assert _mask("серия 4509 номер 123456") == "серия 45** номер ****56"


def test_passport_series_with_combined_number() -> None:
    assert _mask("серия 4509 123456") == "серия 45** ****56"


def test_passport_series_with_no_number() -> None:
    assert _mask("паспорт серия 4509 № 123456") != "паспорт серия 4509 № 123456"


def test_issuer_oufms() -> None:
    text = "выдан ОУФМС России по г. Москве 01.02.2010"
    result = _mask(text)
    assert "ОУФМС" not in result
    assert "Москве" not in result
    assert result.startswith("выдан ")


def test_issuer_otdel_ufms() -> None:
    text = (
        "Паспорт выдан Отделом УФМС России по Московской обл. в Одинцовском р-не, "
        "дата выдачи 12.05.2015"
    )
    result = _mask(text)
    assert "Отделом" not in result
    assert "УФМС" not in result
    assert "дата выдачи" in result


def test_issuer_gu_mvd() -> None:
    text = "кем выдан: ГУ МВД России по г. Санкт-Петербургу; код подразделения 780-001"
    result = _mask(text)
    assert "ГУ" not in result
    assert "МВД" not in result
    assert "код подразделения" in result


def test_issuer_no_organ() -> None:
    assert "PASSPORT_ISSUER" not in _types("выдан 01.02.2010")


def test_issuer_tovar() -> None:
    assert "PASSPORT_ISSUER" not in _types("Товар выдан покупателю")


def test_issuer_date_words_not_organ() -> None:
    assert "PASSPORT_ISSUER" not in _types(
        "выдан третьего августа тысяча девятьсот восемьдесят пятого г."
    )


def test_issuer_cut_on_inn() -> None:
    text = "выдан оуфмс россии по г. самара, инн 5605628738"
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "PASSPORT_ISSUER"]
    assert spans
    assert text[spans[0].start : spans[0].end] == "оуфмс россии по г. самара"


def test_issuer_cut_on_pin() -> None:
    text = "выдан оуфмс россии по г. москва, пин 6232"
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "PASSPORT_ISSUER"]
    assert spans
    assert text[spans[0].start : spans[0].end] == "оуфмс россии по г. москва"


def _span_at(text: str, value: str, pii_type: str) -> None:
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    start = text.index(value)
    end = start + len(value)
    matching = [s for s in spans if s.pii_type == pii_type and s.start == start and s.end == end]
    assert matching, f"no {pii_type} span at {value!r} in {text!r}"


def test_driver_old_format_in_phrase() -> None:
    text = "email александр@yandex.ru, CVV 503, адрес г. челябинск, ВУ 28 вс 464342, ИНН 0379263560"
    _span_at(text, "28 вс 464342", "DRIVER_LICENSE")


def test_division_code_not_from_phone() -> None:
    text = "ТЕЛЕФОН 942 561 81 85, КОД ПОДРАЗДЕЛЕНИЯ 195-542"
    _span_at(text, "195-542", "DIVISION_CODE")
