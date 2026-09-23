from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.policy import Profile
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.settings import Settings
from tests.helpers import PARTIAL_PROFILE

NEVSKY_ADDRESS = "г. Санкт-Петербург, Невский пр-т, д. 28"


def _engine() -> Engine:
    registry = RecognizerRegistry.from_modules(Settings().recognizer_modules)
    return Engine(registry, DefaultMasker(default_type_registry()))


def _mask(text: str) -> str:
    return _engine().mask(text, PARTIAL_PROFILE).text


def _mask_full(text: str) -> str:
    return _engine().mask(text, Profile(name="checker", mask_style="full")).text


def test_full_address() -> None:
    text = "Адрес регистрации: 123456, г. Москва, ул. Ленина, д. 5, кв. 12"
    assert _mask(text) == "Адрес регистрации: ******, г. ******, ул. ******, д. *, кв. **"


def test_address_with_region() -> None:
    text = "проживает по адресу Московская обл., г. Химки, ул. Мира, д. 3к2, кв. 45"
    assert _mask(text) == "проживает по адресу ********** обл., г. *****, ул. ****, д. ***, кв. **"


def test_address_street_after_marker() -> None:
    assert _mask(NEVSKY_ADDRESS) != NEVSKY_ADDRESS


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


def test_street_whole_payload_masked() -> None:
    assert _mask("улица Льва Толстого") == "улица **** ********"


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
    assert _mask(NEVSKY_ADDRESS) == "г. *****-*********, ******* пр-т, д. **"


def test_tverskaya_street() -> None:
    assert (
        _mask("адрес доставки: Тверская улица, д. 7, кв. 3")
        == "адрес доставки: ******** улица, д. *, кв. *"
    )


def test_region_republic_case() -> None:
    text = "проживает по адресу республике татарстан, г. тольятти"
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "ADDRESS"]
    assert any(text[s.start : s.end] == "татарстан" for s in spans)


def test_city_street_house_full() -> None:
    assert _mask_full("Екатеринбург, ул. 8 Марта, 14") == "************, ул. *******, **"


def test_city_street_full() -> None:
    assert _mask_full("Москва, ул. Тверская") == "******, ул. ********"


def test_street_house_after_marker_full() -> None:
    assert _mask_full("Садовая ул., 5") == "******* ул., *"


def test_city_adjective_house_full() -> None:
    assert _mask_full("адрес: Москва, Профсоюзная 12-34") == "адрес: ******, *********** *****"


def test_city_adjective_house_context_full() -> None:
    assert _mask_full("переехал в Подольск, Высотная 7") == "переехал в ********, ******** *"


def test_city_prospekt_house_full() -> None:
    assert _mask_full("Москва, Ленинградский проспект 37") == "******, ************* проспект **"


def test_live_on_prospekt_full() -> None:
    assert (
        _mask_full("живу на Ленинском проспекте 45, кв 12")
        == "живу на ********* проспекте **, кв **"
    )


def test_bank_branch_address_not_masked_full() -> None:
    text = "Отделение Альфа-Банка находится по адресу: Москва, ул. Каланчёвская, д. 27"
    assert _mask_full(text) == text


def test_bank_office_alpha_not_masked() -> None:
    text = "Офис Альфа-Банка по адресу г. Москва, ул. Каланчёвская, д. 27"
    assert _mask(text) == text


def test_atm_sberbank_not_masked() -> None:
    text = "Банкомат Сбербанка: г. Казань, ул. Баумана, д. 10"
    assert _mask(text) == text


def test_bank_office_residence_masked() -> None:
    text = "Перевести в отделение по месту жительства: г. Москва, ул. Ленина, д. 5"
    assert _mask(text) != text


def test_bank_employee_address_masked() -> None:
    text = "Сотрудник банка Иванов живёт по адресу г. Москва, ул. Ленина, д. 5"
    assert "Ленина" not in _mask(text)


def test_moscow_capital_not_masked_full() -> None:
    assert _mask_full("Москва — столица России") == "Москва — столица России"


def test_atm_tverskaya_not_masked_full() -> None:
    assert (
        _mask_full("Банкомат на Тверской не выдаёт наличные")
        == "Банкомат на Тверской не выдаёт наличные"
    )


def test_metro_tverskaya_not_masked_full() -> None:
    assert _mask_full("Станция метро Пушкинская, выход к Тверской улице") == (
        "Станция метро Пушкинская, выход к Тверской улице"
    )


def test_delivery_point_prospekt_not_masked_full() -> None:
    assert _mask_full("Заказ доставят в пункт выдачи на Ленинском проспекте") == (
        "Заказ доставят в пункт выдачи на Ленинском проспекте"
    )


def test_office_address_not_masked() -> None:
    text = (
        "Александр Пушкин работает в офисе на Тверской улице. "
        "Адрес офиса: г. Москва, ул. Тверская, д. 1."
    )
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "ADDRESS"]
    assert spans == []


def test_our_office_address_not_masked() -> None:
    text = "Наш офис расположен по адресу: г. Москва, ул. Тверская, д. 1."
    spans = [s for s in _engine().analyze(text, PARTIAL_PROFILE) if s.pii_type == "ADDRESS"]
    assert spans == []


def test_residence_address_masked() -> None:
    text = "Адрес проживания: г. Москва, ул. Тверская, д. 10, кв. 25."
    assert _mask(text) != text


def test_pgt_ivanino_recognized() -> None:
    assert _mask("пгт. Иванино") != "пгт. Иванино"


def test_ul_lenina_recognized() -> None:
    assert _mask("ул. Ленина") != "ул. Ленина"
