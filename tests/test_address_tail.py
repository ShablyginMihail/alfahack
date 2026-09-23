from pii_guard.core.normalize import Document
from pii_guard.core.service_words import SERVICE_WORDS
from pii_guard.recognizers.address import AddressRecognizer

OFFICE_TRAP_1 = "Наш офис расположен по адресу: г. Москва, ул. Тверская, д. 1."
OFFICE_TRAP_2 = (
    "Александр Пушкин работает в офисе на Тверской улице. "
    "Адрес офиса: г. Москва, ул. Тверская, д. 1."
)
ENTRANCE_CHAIN = "Челябинск, ул. Кирова, д. 23, стр. 2, кв. 67, подъезд 4"
ENTRANCE_AFTER_CHAIN = "Уфа, ул. Ленина, д. 56, кв. 89, 2 подъезд"


def _masked(text: str) -> set[str]:
    doc = Document.from_text(text)
    spans = [s for s in AddressRecognizer().find(doc) if s.score >= 0.5]
    return {text[s.start : s.end] for s in spans}


def test_house_after_street_marker() -> None:
    assert _masked("на ул. Ленина 45") == {"Ленина", "45"}


def test_house_after_street_corps() -> None:
    assert _masked("ул. Строителей 17к3") == {"Строителей", "17к3"}


def test_house_after_street_trailing_word() -> None:
    assert _masked("ул. Садовая 18 течёт батарея") == {"Садовая", "18"}


def test_house_after_street_with_apartment() -> None:
    assert _masked("ул. Ленина 45 кв 12") == {"Ленина", "45", "12"}


def test_house_after_square() -> None:
    assert _masked("Краснодар, Красная площадь, 1") == {"Краснодар", "Красная", "1"}


def test_entrance_in_chain() -> None:
    assert _masked(ENTRANCE_CHAIN) == {"Челябинск", "Кирова", "23", "2", "67", "4"}


def test_entrance_after_in_chain() -> None:
    assert _masked(ENTRANCE_AFTER_CHAIN) == {"Уфа", "Ленина", "56", "89", "2"}


def test_entrance_short_after() -> None:
    assert _masked("кв. 23, 4 под") == {"23", "4"}


def test_street_before_tail() -> None:
    assert _masked("тверь, вокзальная 45, кв 23") == {"тверь", "вокзальная", "45", "23"}


def test_office_trap_1_not_masked() -> None:
    assert _masked(OFFICE_TRAP_1) == set()


def test_office_trap_2_not_masked() -> None:
    assert _masked(OFFICE_TRAP_2) == set()


def test_single_floor_not_masked() -> None:
    assert _masked("живу на 5 этаже") == set()


def test_single_floor_nominative_not_masked() -> None:
    assert _masked("5 этаж") == set()


def test_single_entrance_not_masked() -> None:
    assert _masked("под 2 градуса") == set()


def test_page_number_not_masked() -> None:
    assert _masked("страница 45") == set()


def test_service_words_contain_entrance() -> None:
    assert "подъезд" in SERVICE_WORDS
    assert "под" in SERVICE_WORDS
    assert "этаж" in SERVICE_WORDS
    assert "эт" in SERVICE_WORDS
