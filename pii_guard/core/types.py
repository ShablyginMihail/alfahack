from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PiiType:
    code: str
    label: str
    description: str


BUILTIN_TYPES: tuple[PiiType, ...] = (
    PiiType("PERSON", "ФИО", "Фамилия, имя, отчество"),
    PiiType("BIRTH_DATE", "ДАТА_РОЖДЕНИЯ", "Дата рождения"),
    PiiType("BIRTH_PLACE", "МЕСТО_РОЖДЕНИЯ", "Место рождения"),
    PiiType("PASSPORT", "ПАСПОРТ", "Серия и номер паспорта РФ"),
    PiiType("CITIZENSHIP", "ГРАЖДАНСТВО", "Гражданство"),
    PiiType("PASSPORT_ISSUER", "ОРГАН_ВЫДАЧИ", "Орган, выдавший паспорт"),
    PiiType("DIVISION_CODE", "КОД_ПОДРАЗДЕЛЕНИЯ", "Код подразделения"),
    PiiType("PASSPORT_ISSUE_DATE", "ДАТА_ВЫДАЧИ", "Дата выдачи паспорта"),
    PiiType("DRIVER_LICENSE", "ВУ", "Серия и номер водительского удостоверения"),
    PiiType("ADDRESS", "АДРЕС", "Адрес или его часть"),
    PiiType("EMAIL", "EMAIL", "Электронная почта"),
    PiiType("PHONE", "ТЕЛЕФОН", "Номер телефона"),
    PiiType("INN", "ИНН", "ИНН"),
    PiiType("CARD_NUMBER", "КАРТА", "Номер платёжной карты"),
    PiiType("CVV", "CVV", "CVV/CVC-код"),
    PiiType("PIN", "ПИН", "ПИН-код карты"),
    PiiType("CARDHOLDER", "ДЕРЖАТЕЛЬ", "Имя держателя карты"),
    PiiType("FOREIGN_PASSPORT", "ЗАГРАНПАСПОРТ", "Загранпаспорт РФ"),
    PiiType("SNILS", "СНИЛС", "СНИЛС"),
    PiiType("RESIDENCE_PERMIT", "ВНЖ", "Вид на жительство"),
    PiiType("MILITARY_ID", "ВОЕННЫЙ_БИЛЕТ", "Военный билет"),
    PiiType("BIRTH_CERTIFICATE", "СВИДЕТЕЛЬСТВО_О_РОЖДЕНИИ", "Свидетельство о рождении"),
    PiiType("FOREIGN_NATIONAL_PASSPORT", "ПАСПОРТ_ИНОСТРАНЦА", "Паспорт иностранного гражданина"),
)

CORE_TYPE_CODES: frozenset[str] = frozenset(pii_type.code for pii_type in BUILTIN_TYPES[:17])


class TypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, PiiType] = {}

    def register(self, pii_type: PiiType) -> None:
        self._types[pii_type.code] = pii_type

    def get(self, code: str) -> PiiType:
        return self._types[code]

    def label(self, code: str) -> str:
        return self._types[code].label

    def codes(self) -> frozenset[str]:
        return frozenset(self._types)


def default_type_registry() -> TypeRegistry:
    registry = TypeRegistry()
    for pii_type in BUILTIN_TYPES:
        registry.register(pii_type)
    return registry
