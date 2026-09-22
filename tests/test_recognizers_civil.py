from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.policy import CHECKER_PROFILE
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


def test_birth_place_city() -> None:
    assert _mask("место рождения: г. Ленинград") == "место рождения: г. *********"


def test_birth_place_region() -> None:
    text = "Место рождения — Саратовская обл., с. Ивановка"
    assert _mask(text) != text


def test_birth_place_urozhenec() -> None:
    assert _mask("уроженец Казани") == "уроженец ******"


def test_born_in_city() -> None:
    assert "BIRTH_PLACE" in _types("родился в Новосибирске")


def test_born_in_year_not_place() -> None:
    assert "BIRTH_PLACE" not in _types("родился в 1985 году")


def test_born_in_month_not_place() -> None:
    assert "BIRTH_PLACE" not in _types("родилась в марте")


def test_citizenship_rf() -> None:
    assert _mask("гражданство: РФ") == "гражданство: **"


def test_citizenship_russian_federation() -> None:
    assert "CITIZENSHIP" in _types("гражданин Российской Федерации")


def test_citizenship_belarus() -> None:
    assert "CITIZENSHIP" in _types("гражданка Республики Беларусь")


def test_citizenship_kazakhstan() -> None:
    assert "CITIZENSHIP" in _types("гражданство Казахстана")


def test_citizenship_adjective() -> None:
    assert "CITIZENSHIP" in _types("российское гражданство")


def test_country_without_label_not_masked() -> None:
    assert _mask("Россия — большая страна") == "Россия — большая страна"


def test_case_insensitive() -> None:
    assert _mask("МЕСТО РОЖДЕНИЯ: Г. МОСКВА") == "МЕСТО РОЖДЕНИЯ: Г. ******"
    assert _mask("ГРАЖДАНСТВО: РФ") == "ГРАЖДАНСТВО: **"
