from __future__ import annotations

import pytest

from pii_guard.core.types import (
    BUILTIN_TYPES,
    CORE_TYPE_CODES,
    PiiType,
    default_type_registry,
)

EXPECTED_LABELS = {
    "PERSON": "ФИО",
    "BIRTH_DATE": "ДАТА_РОЖДЕНИЯ",
    "BIRTH_PLACE": "МЕСТО_РОЖДЕНИЯ",
    "PASSPORT": "ПАСПОРТ",
    "CITIZENSHIP": "ГРАЖДАНСТВО",
    "PASSPORT_ISSUER": "ОРГАН_ВЫДАЧИ",
    "DIVISION_CODE": "КОД_ПОДРАЗДЕЛЕНИЯ",
    "PASSPORT_ISSUE_DATE": "ДАТА_ВЫДАЧИ",
    "DRIVER_LICENSE": "ВУ",
    "ADDRESS": "АДРЕС",
    "EMAIL": "EMAIL",
    "PHONE": "ТЕЛЕФОН",
    "INN": "ИНН",
    "CARD_NUMBER": "КАРТА",
    "CVV": "CVV",
    "PIN": "ПИН",
    "CARDHOLDER": "ДЕРЖАТЕЛЬ",
}


def test_all_core_codes_present_with_labels() -> None:
    registry = default_type_registry()
    assert registry.codes() == CORE_TYPE_CODES | {
        "FOREIGN_PASSPORT",
        "SNILS",
        "RESIDENCE_PERMIT",
        "MILITARY_ID",
        "BIRTH_CERTIFICATE",
        "FOREIGN_NATIONAL_PASSPORT",
        "OMS_POLICY",
    }
    for code, label in EXPECTED_LABELS.items():
        assert registry.get(code).label == label
        assert registry.label(code) == label


def test_core_type_codes_has_17_codes() -> None:
    assert len(CORE_TYPE_CODES) == 17
    assert frozenset(EXPECTED_LABELS) == CORE_TYPE_CODES


def test_unknown_code_raises_key_error() -> None:
    registry = default_type_registry()
    with pytest.raises(KeyError):
        registry.get("UNKNOWN")
    with pytest.raises(KeyError):
        registry.label("UNKNOWN")


def test_register_new_type() -> None:
    registry = default_type_registry()
    new_type = PiiType("NEW_TYPE", "НОВЫЙ", "Описание")
    registry.register(new_type)
    assert registry.get("NEW_TYPE") is new_type
    assert registry.label("NEW_TYPE") == "НОВЫЙ"
    assert "NEW_TYPE" in registry.codes()


def test_register_replaces_existing() -> None:
    registry = default_type_registry()
    replacement = PiiType("PASSPORT", "ДРУГОЙ", "Другое описание")
    registry.register(replacement)
    assert registry.get("PASSPORT") is replacement


def test_builtin_types_are_frozen() -> None:
    assert all(isinstance(t, PiiType) for t in BUILTIN_TYPES)
    assert len(BUILTIN_TYPES) == 24
