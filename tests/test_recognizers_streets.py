from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.settings import Settings
from tests.helpers import PARTIAL_PROFILE

DELIVERY_TVERSKAYA = "доставку на Тверскую 17"
ADRESOK_LENINA = "адресок Ленина 67 подъезд 1"
TYUMEN_REPUBLIKI = "Тюмень, Республики 15"
VICTORY_75 = "в честь Дня Победы 75 лет"
VICTORY_9_MAY = "Победы 9 мая"
MIRA_2 = "Мира 2 раза звонила"
OFFICE_ADDRESS = "Наш офис расположен по адресу: г. Москва, ул. Тверская, д. 1."


def _engine() -> Engine:
    registry = RecognizerRegistry.from_modules(Settings().recognizer_modules)
    return Engine(registry, DefaultMasker(default_type_registry()))


def _spans(text: str) -> list[str]:
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "ADDRESS"]
    return [text[s.start : s.end] for s in spans]


def test_dictionary_street_indirect_case() -> None:
    assert _spans(DELIVERY_TVERSKAYA) == ["Тверскую", "17"]


def test_surname_street_with_house_and_entrance() -> None:
    assert _spans(ADRESOK_LENINA) == ["Ленина", "67", "1"]


def test_city_and_non_dictionary_street() -> None:
    assert _spans(TYUMEN_REPUBLIKI) == ["Тюмень", "Республики", "15"]


def test_unit_words_after_number() -> None:
    assert _spans(VICTORY_75) == []
    assert _spans(VICTORY_9_MAY) == []
    assert _spans(MIRA_2) == []


def test_office_address_not_masked() -> None:
    assert _spans(OFFICE_ADDRESS) == []


def test_module_in_settings() -> None:
    assert "pii_guard.recognizers.streets" in Settings().recognizer_modules
