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


def test_birth_place_span_starts_at_value() -> None:
    text = "Место рождения — Саратовская обл., с. Ивановка"
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "BIRTH_PLACE"]
    assert spans
    assert text[spans[0].start : spans[0].end].startswith("Саратовская")


def test_citizenship_genitive() -> None:
    assert "CITIZENSHIP" in _types("гражданка украины")
    assert "CITIZENSHIP" in _types("Гражданин Армении")
    assert "CITIZENSHIP" in _types("Гражданство: Грузии")


def test_citizenship_kyrgyz_republic() -> None:
    _span_at("является гражданкой Кыргызской Республики", "Кыргызской Республики", "CITIZENSHIP")


def test_citizenship_kyrgyz_genitive() -> None:
    _span_at("гражданином Киргизии", "Киргизии", "CITIZENSHIP")


def test_birth_place_cut_on_pin() -> None:
    text = "МЕСТО РОЖДЕНИЯ Г. САРАТОВ, ПИН 7520"
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "BIRTH_PLACE"]
    assert spans
    assert text[spans[0].start : spans[0].end] == "САРАТОВ"


def _span_at(text: str, value: str, pii_type: str) -> None:
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    start = text.index(value)
    end = start + len(value)
    matching = [s for s in spans if s.pii_type == pii_type and s.start == start and s.end == end]
    assert matching, f"no {pii_type} span at {value!r} in {text!r}"


def test_born_date_then_place() -> None:
    text = "родился 12 марта 1985 года в г. Саратов"
    _span_at(text, "Саратов", "BIRTH_PLACE")
    _span_at(text, "12 марта 1985", "BIRTH_DATE")


def test_born_year_then_place() -> None:
    text = "родилась в 1990 году в Казани"
    _span_at(text, "Казани", "BIRTH_PLACE")
    _span_at(text, "1990", "BIRTH_DATE")


def test_born_numeric_date_then_place() -> None:
    text = "Родился 03.12.1985 в городе Самаре"
    _span_at(text, "Самаре", "BIRTH_PLACE")


def test_born_place_with_personal_context() -> None:
    text = "Клиент Иванов родился в Москве"
    _span_at(text, "Москве", "BIRTH_PLACE")


def test_public_figure_birth_place_not_masked() -> None:
    assert "BIRTH_PLACE" not in _types("поэт Александр Пушкин родился в Москве")
    assert "BIRTH_PLACE" not in _types("Юрий Гагарин родился 9 марта 1934 года в Клушине")
