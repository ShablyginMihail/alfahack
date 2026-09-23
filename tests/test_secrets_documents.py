from pii_guard.core.engine import Engine
from pii_guard.core.masking import DefaultMasker
from pii_guard.core.registry import RecognizerRegistry
from pii_guard.core.types import default_type_registry
from pii_guard.recognizers.documents import recognizers as documents_recognizers
from pii_guard.recognizers.numeric import recognizers as numeric_recognizers
from tests.helpers import PARTIAL_PROFILE

CVV_FAR_1 = "Назовите CVC-код для завершения транзакции, мой 901"
CVV_FAR_2 = "Меня заставляют назвать CVC код, не знаю что делать, это 398"
CVV_FAR_3 = "оператор просит CVC, это нормально? вот 012"
CVV_BACK_1 = "код сзади карты 456"
CVV_BACK_2 = "код сзади на карте 456"
CVV_BACK_3 = "код на задней стороне 456"
CVV_BACK_4 = "код с задней стороны 456"
CVV_BACK_5 = "код на обороте карты 456"
CVV_BACK_6 = "код с оборота 456"
CVV_CONFIRM_PAY = "оплата картой, код подтверждения 382"
CVV_CONFIRM_SMS_PAY = "покупка, код из смс 382"
CVV_CONFIRM_NO_PAY = "код подтверждения 382"
CVV_CONFIRM_SMS_NO_PAY = "код из смс 382"
CVV_SHORT = "CVV: 12."
CVV_ERROR = "код ошибки 404"
CVV_LABEL_ORDER = "Код безопасности не нужен, заказ 123 доставлен вчера"
CVV_LABEL_NUMBER = "Никогда не сообщайте CVV никому. Звоните по номеру 900"
CVV_KEEP_CODE = "зачем CVC нужен? код 453"

PASSPORT_SERIES_ACC = "укажите серию и номер: 2300515101"
PASSPORT_SERIES_INSTR = "укажите серией и номером: 2300515101"
PASSPORT_FAR_1 = "курьер просит паспорт для получения заказа. вот данные: 5506789012"
PASSPORT_FAR_2 = "заменить паспорт по возрасту в отделении МВД, старый 1616497506"
PASSPORT_SPACED = "4509 123456"
PASSPORT_SPACED_ORDER = "Номер заказа: 4510 123456"
PASSPORT_RUN_ORDER = "Номер заказа: 4510123456."
PASSPORT_NUMBER_WORDS = "паспорт, номер был 122648"
PASSPORT_NUMBER_COLON = "паспорт, номер: 122648"
PASSPORT_SERIES_TRAP = "Серия 451 номер 12345."
PASSPORT_NUMBER_QUEUE = "Номер паспорта не нужен, ваш номер в очереди 123456"
PASSPORT_NUMBER_WAS = "потерял паспорт, серию не помню, но номер был 122648"

INN_INSTR = "риелтор с инном 772501234504"
INN_ACC = "риелтор с инну 772501234504"
INN_PREP = "риелтор с инне 772501234504"
INN_HYPHEN = "риелтор с инн-у 772501234504"
INN_NAME = "инна 772501234504"


def _engine() -> Engine:
    registry = RecognizerRegistry()
    for recognizer in numeric_recognizers():
        registry.register(recognizer)
    for recognizer in documents_recognizers():
        registry.register(recognizer)
    return Engine(registry, DefaultMasker(default_type_registry()))


def _types(text: str) -> set[str]:
    return {span.pii_type for span in _engine().analyze(text, PARTIAL_PROFILE)}


def _span_at(text: str, value: str, pii_type: str) -> None:
    spans = _engine().analyze(text, PARTIAL_PROFILE)
    start = text.index(value)
    end = start + len(value)
    matching = [s for s in spans if s.pii_type == pii_type and s.start == start and s.end == end]
    assert matching, f"no {pii_type} span at {value!r} in {text!r}"


def test_cvv_far_keyword_1() -> None:
    _span_at(CVV_FAR_1, "901", "CVV")


def test_cvv_far_keyword_2() -> None:
    _span_at(CVV_FAR_2, "398", "CVV")


def test_cvv_far_keyword_3() -> None:
    _span_at(CVV_FAR_3, "012", "CVV")


def test_cvv_back_context_words() -> None:
    for text in (
        CVV_BACK_1,
        CVV_BACK_2,
        CVV_BACK_3,
        CVV_BACK_4,
        CVV_BACK_5,
        CVV_BACK_6,
    ):
        _span_at(text, "456", "CVV")


def test_cvv_confirm_with_payment() -> None:
    _span_at(CVV_CONFIRM_PAY, "382", "CVV")
    _span_at(CVV_CONFIRM_SMS_PAY, "382", "CVV")


def test_cvv_confirm_typo_with_payment() -> None:
    _span_at("оплата картой, код потверждения 382", "382", "CVV")


def test_cvv_confirm_without_payment_not_masked() -> None:
    assert "CVV" not in _types(CVV_CONFIRM_NO_PAY)
    assert "CVV" not in _types(CVV_CONFIRM_SMS_NO_PAY)


def test_cvv_confirm_short_not_masked() -> None:
    assert "CVV" not in _types(CVV_SHORT)


def test_cvv_error_code_not_masked() -> None:
    assert "CVV" not in _types(CVV_ERROR)


def test_cvv_label_order_not_masked() -> None:
    assert "CVV" not in _types(CVV_LABEL_ORDER)


def test_cvv_label_number_not_masked() -> None:
    assert "CVV" not in _types(CVV_LABEL_NUMBER)


def test_cvv_keep_code() -> None:
    _span_at(CVV_KEEP_CODE, "453", "CVV")


def test_passport_series_accusative() -> None:
    _span_at(PASSPORT_SERIES_ACC, "2300515101", "PASSPORT")


def test_passport_series_instrumental() -> None:
    _span_at(PASSPORT_SERIES_INSTR, "2300515101", "PASSPORT")


def test_passport_far_context_1() -> None:
    _span_at(PASSPORT_FAR_1, "5506789012", "PASSPORT")


def test_passport_far_context_2() -> None:
    _span_at(PASSPORT_FAR_2, "1616497506", "PASSPORT")


def test_passport_spaced_self_sign() -> None:
    _span_at(PASSPORT_SPACED, "4509 123456", "PASSPORT")


def test_passport_spaced_with_order_not_masked() -> None:
    assert "PASSPORT" not in _types(PASSPORT_SPACED_ORDER)


def test_passport_run_order_not_masked() -> None:
    assert "PASSPORT" not in _types(PASSPORT_RUN_ORDER)


def test_passport_number_words() -> None:
    _span_at(PASSPORT_NUMBER_WORDS, "122648", "PASSPORT")


def test_passport_number_colon() -> None:
    _span_at(PASSPORT_NUMBER_COLON, "122648", "PASSPORT")


def test_passport_series_trap_not_masked() -> None:
    assert "PASSPORT" not in _types(PASSPORT_SERIES_TRAP)


def test_passport_number_queue_not_masked() -> None:
    assert "PASSPORT" not in _types(PASSPORT_NUMBER_QUEUE)


def test_passport_number_was() -> None:
    _span_at(PASSPORT_NUMBER_WAS, "122648", "PASSPORT")


def test_inn_instrumental() -> None:
    _span_at(INN_INSTR, "772501234504", "INN")


def test_inn_accusative() -> None:
    _span_at(INN_ACC, "772501234504", "INN")


def test_inn_prepositional() -> None:
    _span_at(INN_PREP, "772501234504", "INN")


def test_inn_hyphen() -> None:
    _span_at(INN_HYPHEN, "772501234504", "INN")


def test_inn_name_not_context() -> None:
    assert "INN" not in _types(INN_NAME)
