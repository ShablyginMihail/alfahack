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


def _has_person(text: str) -> bool:
    return any(span.pii_type == "PERSON" for span in _engine().analyze(text, PARTIAL_PROFILE))


def test_contract_example() -> None:
    text = "Клиент Иванов Иван Иванович, паспорт 4509 123456"
    assert _mask(text) == "Клиент И. И. И., паспорт 45** ****56"


def test_full_name_lowercase() -> None:
    assert _has_person("иванов иван иванович")


def test_full_name_uppercase() -> None:
    assert _has_person("ИВАНОВ ИВАН ИВАНОВИЧ")


def test_name_patr_surn() -> None:
    assert _has_person("Иван Иванович Иванов")


def test_female_name() -> None:
    assert _has_person("Иванова Мария Петровна")


def test_dative_case() -> None:
    assert _has_person("Иванову Ивану Ивановичу")


def test_surn_initials() -> None:
    assert _has_person("Петров П.П.")


def test_initials_surn() -> None:
    assert _has_person("П. П. Петров")


def test_name_patr() -> None:
    assert _has_person("Анна Сергеевна")


def test_name_surn() -> None:
    assert _has_person("Сергей Кузнецов")


def test_single_surn_with_context() -> None:
    assert _mask("Клиент Смирнов позвонил") == "Клиент С. позвонил"


def test_single_unambiguous_surname_masked() -> None:
    assert _mask("Смирнов позвонил") == "С. позвонил"


def test_poet_pushkin_not_masked() -> None:
    assert not _has_person("поэт Александр Пушкин")


def test_pushkin_roman_not_masked() -> None:
    assert not _has_person("Александр Сергеевич Пушкин написал роман")


def test_tolstoy_street_not_masked() -> None:
    assert not _has_person("улица Льва Толстого")


def test_peter_monument_not_masked() -> None:
    assert not _has_person("памятник Петру Первому")


def test_client_pushkin_masked() -> None:
    assert _has_person("клиент Александр Пушкин, паспорт 4509 123456")


def test_ordinary_words_not_masked() -> None:
    assert not _has_person("Вера в успех")
    assert not _has_person("Роман о любви")
    assert not _has_person("Надежда умирает последней")
    assert not _has_person("Слава труду")


def test_saltykov_shchedrin_not_masked() -> None:
    assert not _has_person("писатель Салтыков-Щедрин")


def _has_cardholder(text: str) -> bool:
    return any(span.pii_type == "CARDHOLDER" for span in _engine().analyze(text, PARTIAL_PROFILE))


def test_cardholder_latin() -> None:
    assert _mask("держатель карты IVAN IVANOV") == "держатель карты I. I."


def test_cardholder_name_on_card() -> None:
    assert _has_cardholder("имя на карте: ivan ivanov")


def test_cardholder_with_card_number() -> None:
    assert _has_cardholder("карта 4276 1234 5678 9012, SERGEY PETROV")


def test_cardholder_cyrillic() -> None:
    assert _has_cardholder("держатель карты Иванов Иван")


def test_latin_name_without_context_person() -> None:
    assert _has_person("IVAN PETROV")


def test_latin_stop_words_not_masked() -> None:
    assert not _has_person("VISA CARD")
    assert not _has_person("Mastercard Gold")


def test_inn_not_person() -> None:
    result = _mask("Заемщик Кузнецов Петр, ИНН 500100732259")
    assert "ИНН" in result


def test_single_letter_not_initial_before_city() -> None:
    assert not _has_person("Место рождения: г. саратов")


def test_cardholder_vs_personal_context() -> None:
    text = "Держатель Ivan Ivanov, Клиент Петров Владимир Владимирович"
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    cardholder = [s for s in spans if s.pii_type == "CARDHOLDER"]
    person = [s for s in spans if s.pii_type == "PERSON"]
    assert cardholder and person
    assert text[cardholder[0].start : cardholder[0].end] == "Ivan Ivanov"
    assert text[person[0].start : person[0].end] == "Петров Владимир Владимирович"


def _span_at(text: str, value: str, pii_type: str) -> None:
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    start = text.index(value)
    end = start + len(value)
    matching = [s for s in spans if s.pii_type == pii_type and s.start == start and s.end == end]
    assert matching, f"no {pii_type} span at {value!r} in {text!r}"


def test_single_name_dative() -> None:
    _span_at("Позвоните Марии по номеру 8 999 123 45 67", "Марии", "PERSON")


def test_single_surname_dative() -> None:
    _span_at("Передайте Смирнову, что карта готова", "Смирнову", "PERSON")


def test_single_name_not_person() -> None:
    assert not _has_person("Роман прочитан за вечер")
    assert not _has_person("Встреча в Москве перенесена")
    assert not _has_person("Пушкин написал много стихов")
