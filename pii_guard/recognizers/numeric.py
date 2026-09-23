from __future__ import annotations

import re
from collections.abc import Sequence

from pii_guard.core.context import compile_keywords
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.base import OMS_WORDS, PatternRule, RegexRecognizer
from pii_guard.recognizers.validators import inn_valid, luhn_valid

EMAIL_RE = re.compile(r"(?<!\w)[\w.+-]+@[\w.-]+\.[\w-]+(?!\w)")

PHONE_PLUS7_RE = re.compile(
    r"(?<!\d)\+7[\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"
)
PHONE_8_7_RE = re.compile(
    r"(?<!\d)[78][\s.\-]*\(?\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"
)
PHONE_NO_CODE_RE = re.compile(r"(?<!\d)\(?9\d{2}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)")
PHONE_INTL_RE = re.compile(
    r"(?<!\d)\+\d{1,3}[\s.\-]*\(?\d{2,4}\)?[\s.\-]*\d{2,4}[\s.\-]*\d{2,4}[\s.\-]*\d{2,4}(?!\d)"
)

CARD_GROUPED_RE = re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)")
CARD_RUN_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
CARD_RUN_16_RE = re.compile(r"(?<!\d)[2-6]\d{15}(?!\d)")

INN_RUN_10_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
INN_RUN_12_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
INN_SEPARATED_RE = re.compile(r"(?<!\d)\d{2,4}[\s-]\d{2,4}[\s-]\d{2,6}(?!\d)")
CVV_RE = re.compile(r"(?<!\d)(?<!(?<![^\W\d_])\d[\s-])\d{3,4}(?![\s-]\d)(?!\d)")
PIN_RE = re.compile(r"(?<!\d)(?<!(?<![^\W\d_])\d[\s-])\d{4,6}(?![\s-]\d)(?!\d)")

PHONE_CONTEXT = compile_keywords(
    ["тел", "телефон", "моб", "мобил", "звон", "whatsapp", "telegram", "контакт"]
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
        *OMS_WORDS,
    ]
)
INN_CONTEXT = compile_keywords(["инн"])
INN_ORG_NEGATIVE = compile_keywords(
    [
        "организации",
        "ооо",
        "оао",
        "зао",
        "пао",
        "ао",
        "юр. лица",
        "юридического лица",
        "компании",
        "предприятия",
        "кпп",
        "банка",
    ]
)
CVV_CONTEXT = compile_keywords(
    [
        "cvv",
        "cvc",
        "cvv2",
        "cvc2",
        "код безопасности",
        "секретный код",
        "три цифры",
        "на обороте",
        "оборотной стороне",
        "обратной стороне",
        "трехзначный код",
        "cvv-код",
        "cvc-код",
        "код cvv",
        "код cvc",
    ]
)
PIN_CONTEXT = compile_keywords(["пин", "pin", "пинкод", "pin code"])


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
            context_bonus=0.5,
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
        PatternRule(
            "CARD_NUMBER",
            CARD_RUN_16_RE,
            0.5,
            negative=CARD_NEGATIVE,
            negative_penalty=0.4,
        ),
    )


def _inn_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "INN",
            INN_RUN_12_RE,
            0.2,
            validator=inn_valid,
            validator_bonus=0.25,
            context=INN_CONTEXT,
            context_bonus=0.45,
            context_window=30,
        ),
        PatternRule(
            "INN",
            INN_RUN_10_RE,
            0.2,
            validator=inn_valid,
            validator_bonus=0.25,
            context=INN_CONTEXT,
            context_bonus=0.45,
            context_window=30,
            negative=INN_ORG_NEGATIVE,
            negative_penalty=0.6,
        ),
        PatternRule(
            "INN",
            INN_SEPARATED_RE,
            0.3,
            context=INN_CONTEXT,
            context_bonus=0.45,
            context_window=8,
            context_direction="before",
        ),
    )


def _cvv_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "CVV",
            CVV_RE,
            0.1,
            context=CVV_CONTEXT,
            context_bonus=0.65,
            context_window=25,
            context_direction="before",
        ),
    )


def _pin_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "PIN",
            PIN_RE,
            0.1,
            context=PIN_CONTEXT,
            context_bonus=0.65,
            context_window=60,
            context_direction="before",
        ),
        PatternRule(
            "PIN",
            PIN_RE,
            0.1,
            context=PIN_CONTEXT,
            context_bonus=0.65,
            context_window=15,
            context_direction="after",
        ),
    )


def recognizers() -> list[Recognizer]:
    return [
        RegexRecognizer("email", [PatternRule("EMAIL", EMAIL_RE, 0.95)]),
        RegexRecognizer("phone", _phone_rules()),
        RegexRecognizer("card", _card_rules()),
        RegexRecognizer("inn", _inn_rules()),
        RegexRecognizer("cvv", _cvv_rules()),
        RegexRecognizer("pin", _pin_rules()),
    ]
