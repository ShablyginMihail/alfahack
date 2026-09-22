from __future__ import annotations

import re
from collections.abc import Sequence

from pii_guard.core.context import compile_keywords
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.base import PatternRule, RegexRecognizer
from pii_guard.recognizers.validators import luhn_valid

EMAIL_RE = re.compile(r"(?<!\w)[\w.+-]+@[\w.-]+\.[\w-]+(?!\w)")

PHONE_PLUS7_RE = re.compile(
    r"(?<!\d)\+7[\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"
)
PHONE_8_7_RE = re.compile(
    r"(?<!\d)(?:8|7)[\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"
)
PHONE_NO_CODE_RE = re.compile(r"(?<!\d)\(?9\d{2}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)")
PHONE_INTL_RE = re.compile(
    r"(?<!\d)\+\d{1,3}[\s.\-]*\(?\d{2,4}\)?[\s.\-]*\d{2,4}[\s.\-]*\d{2,4}[\s.\-]*\d{2,4}(?!\d)"
)

CARD_GROUPED_RE = re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)")
CARD_RUN_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")

PHONE_CONTEXT = compile_keywords(
    ["тел", "телефон", "моб", "звон", "whatsapp", "telegram", "контакт"]
)
CARD_CONTEXT = compile_keywords(["карт", "card", "visa", "mastercard", "мир", "maestro"])
CARD_NEGATIVE = compile_keywords(
    [
        "огрн",
        "огрнип",
        "окпо",
        "кпп",
        "бик",
        "счет",
        "р/с",
        "к/с",
        "лицев",
        "договор",
        "заказ",
        "накладн",
        "трек",
    ]
)


def _phone_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "PHONE",
            PHONE_PLUS7_RE,
            0.85,
            context=PHONE_CONTEXT,
            context_bonus=0.3,
        ),
        PatternRule(
            "PHONE",
            PHONE_8_7_RE,
            0.6,
            context=PHONE_CONTEXT,
            context_bonus=0.3,
        ),
        PatternRule(
            "PHONE",
            PHONE_NO_CODE_RE,
            0.35,
            context=PHONE_CONTEXT,
            context_bonus=0.3,
        ),
        PatternRule(
            "PHONE",
            PHONE_INTL_RE,
            0.7,
            context=PHONE_CONTEXT,
            context_bonus=0.3,
        ),
    )


def _card_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "CARD_NUMBER",
            CARD_GROUPED_RE,
            0.5,
            validator=luhn_valid,
            validator_bonus=0.35,
            context=CARD_CONTEXT,
            context_bonus=0.3,
            negative=CARD_NEGATIVE,
            negative_penalty=0.4,
        ),
        PatternRule(
            "CARD_NUMBER",
            CARD_RUN_RE,
            0.35,
            validator=luhn_valid,
            validator_bonus=0.35,
            context=CARD_CONTEXT,
            context_bonus=0.3,
            negative=CARD_NEGATIVE,
            negative_penalty=0.4,
        ),
    )


def recognizers() -> list[Recognizer]:
    return [
        RegexRecognizer("email", [PatternRule("EMAIL", EMAIL_RE, 0.95)]),
        RegexRecognizer("phone", _phone_rules()),
        RegexRecognizer("card", _card_rules()),
    ]
