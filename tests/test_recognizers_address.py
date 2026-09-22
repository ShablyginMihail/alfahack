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


def test_full_address() -> None:
    text = "Адрес регистрации: 123456, г. Москва, ул. Ленина, д. 5, кв. 12"
    assert _mask(text) == "Адрес регистрации: ******, г. ******, ул. ******, д. *, кв. **"


def test_address_with_region() -> None:
    text = "проживает по адресу Московская обл., г. Химки, ул. Мира, д. 3к2, кв. 45"
    assert _mask(text) == "проживает по адресу ********** обл., г. *****, ул. ****, д. ***, кв. **"


def test_address_street_after_marker() -> None:
    assert (
        _mask("г. Санкт-Петербург, Невский пр-т, д. 28")
        != "г. Санкт-Петербург, Невский пр-т, д. 28"
    )


def test_address_street_with_numbers() -> None:
    text = "ул. 1-я Тверская-Ямская, дом 12, корп. 2, стр. 1"
    assert _mask(text) != text


def test_case_insensitive() -> None:
    assert _mask("Г. МОСКВА, УЛ. ЛЕНИНА, Д. 5") == "Г. ******, УЛ. ******, Д. *"


def test_city_without_marker_with_context() -> None:
    assert _mask("клиент проживает в Казани") == "клиент проживает в ******"


def test_city_without_marker_no_context() -> None:
    assert _mask("Казань — столица Татарстана") == "Казань — столица Татарстана"


def test_bank_branch_not_masked() -> None:
    text = "Отделение банка находится по адресу: г. Москва, ул. Тверская, д. 10"
    assert _mask(text) == text


def test_atm_not_masked() -> None:
    assert _mask("Банкомат на ул. Ленина, д. 1") == "Банкомат на ул. Ленина, д. 1"


def test_city_no_context_not_masked() -> None:
    assert _mask("Москва — крупный город") == "Москва — крупный город"


def test_street_single_not_masked() -> None:
    assert _mask("улица Льва Толстого") == "улица Льва Толстого"


def test_price_index_not_masked() -> None:
    assert _mask("индекс цен 123456") == "индекс цен 123456"


def test_postal_code_with_index() -> None:
    assert _mask("индекс 123456") == "индекс ******"


def test_meeting_place_not_masked() -> None:
    assert _mask("Встретимся у д. 5 на пл. Революции") == "Встретимся у д. 5 на пл. Революции"


def test_live_in_city_on_street() -> None:
    assert (
        _mask("Я живу в Екатеринбурге на улице Малышева")
        == "Я живу в ************* на улице ********"
    )


def test_house_and_apartment() -> None:
    assert _mask("проживает в доме 5, квартира 12") == "проживает в доме *, квартира **"


def test_nevsky_prospekt() -> None:
    assert (
        _mask("г. Санкт-Петербург, Невский пр-т, д. 28")
        == "г. *****-*********, ******* пр-т, д. **"
    )


def test_tverskaya_street() -> None:
    assert (
        _mask("адрес доставки: Тверская улица, д. 7, кв. 3")
        == "адрес доставки: ******** улица, д. *, кв. *"
    )


def test_region_republic_case() -> None:
    text = "проживает по адресу республике татарстан, г. тольятти"
    spans = [s for s in _engine().analyze(text, CHECKER_PROFILE) if s.pii_type == "ADDRESS"]
    assert any(text[s.start : s.end] == "татарстан" for s in spans)
