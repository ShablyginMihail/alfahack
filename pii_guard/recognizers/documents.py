from __future__ import annotations

import re
from collections.abc import Sequence

from pii_guard.core.context import compile_keywords
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.base import PatternRule, RegexRecognizer
from pii_guard.recognizers.validators import snils_valid

PASSPORT_COMBINED_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}[\s-]?(?:№\s*)?\d{6}(?!\d)")
PASSPORT_RUN_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
PASSPORT_SERIES_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}(?!\d)")
PASSPORT_NUMBER_RE = re.compile(r"(?<!\d)\d{6}(?!\d)")

DIVISION_CODE_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}(?!\d)")

DRIVER_COMBINED_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}[\s-]?\d{6}(?!\d)")
DRIVER_OLD_RE = re.compile(r"(?<!\d)\d{2}[\s-]?[А-Яа-яЁё]{2}[\s-]?\d{6}(?!\d)")
DRIVER_SERIES_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}(?!\d)")
DRIVER_NUMBER_RE = re.compile(r"(?<!\d)\d{6}(?!\d)")

SNILS_GROUPED_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}[\s-]\d{3}[\s-]?\d{2}(?!\d)")
SNILS_RUN_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")

FOREIGN_PASSPORT_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{7}(?!\d)")

PASSPORT_CONTEXT = compile_keywords(["паспорт", "серия", "серии", "номер паспорта"])
DIVISION_CONTEXT = compile_keywords(["код подразделения", "подразделени", "код подр", "к/п"])
DIVISION_PASSPORT_CONTEXT = compile_keywords(["паспорт", "выдан"])
DRIVER_CONTEXT = compile_keywords(["водительск", "ву", "в/у", "права", "удостоверени"])
SNILS_CONTEXT = compile_keywords(["снилс", "страхов"])
FOREIGN_CONTEXT = compile_keywords(["загран", "заграничн"])


def _passport_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "PASSPORT",
            PASSPORT_COMBINED_RE,
            0.45,
            context=PASSPORT_CONTEXT,
            context_bonus=0.45,
        ),
        PatternRule(
            "PASSPORT",
            PASSPORT_RUN_RE,
            0.2,
            context=PASSPORT_CONTEXT,
            context_bonus=0.45,
        ),
        PatternRule(
            "PASSPORT",
            PASSPORT_SERIES_RE,
            0.45,
            context=PASSPORT_CONTEXT,
            context_bonus=0.45,
            part="series",
        ),
        PatternRule(
            "PASSPORT",
            PASSPORT_NUMBER_RE,
            0.45,
            context=PASSPORT_CONTEXT,
            context_bonus=0.45,
            part="number",
        ),
    )


def _division_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "DIVISION_CODE",
            DIVISION_CODE_RE,
            0.3,
            context=DIVISION_CONTEXT,
            context_bonus=0.5,
        ),
        PatternRule(
            "DIVISION_CODE",
            DIVISION_CODE_RE,
            0.3,
            context=DIVISION_PASSPORT_CONTEXT,
            context_bonus=0.25,
        ),
    )


def _driver_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_COMBINED_RE,
            0.2,
            context=DRIVER_CONTEXT,
            context_bonus=0.5,
        ),
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_OLD_RE,
            0.2,
            context=DRIVER_CONTEXT,
            context_bonus=0.5,
        ),
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_SERIES_RE,
            0.2,
            context=DRIVER_CONTEXT,
            context_bonus=0.5,
            part="series",
        ),
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_NUMBER_RE,
            0.2,
            context=DRIVER_CONTEXT,
            context_bonus=0.5,
            part="number",
        ),
    )


def _snils_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "SNILS",
            SNILS_GROUPED_RE,
            0.6,
            validator=snils_valid,
            validator_bonus=0.3,
            context=SNILS_CONTEXT,
            context_bonus=0.4,
        ),
        PatternRule(
            "SNILS",
            SNILS_RUN_RE,
            0.15,
            validator=snils_valid,
            validator_bonus=0.3,
            context=SNILS_CONTEXT,
            context_bonus=0.4,
        ),
    )


def _foreign_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "FOREIGN_PASSPORT",
            FOREIGN_PASSPORT_RE,
            0.2,
            context=FOREIGN_CONTEXT,
            context_bonus=0.5,
        ),
    )


def recognizers() -> list[Recognizer]:
    return [
        RegexRecognizer("passport", _passport_rules()),
        RegexRecognizer("division_code", _division_rules()),
        RegexRecognizer("driver_license", _driver_rules()),
        RegexRecognizer("snils", _snils_rules()),
        RegexRecognizer("foreign_passport", _foreign_rules()),
    ]
