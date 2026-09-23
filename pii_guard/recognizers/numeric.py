from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.base import OMS_WORDS, PatternRule, RegexRecognizer
from pii_guard.recognizers.validators import inn_valid, luhn_valid

SERVICE_LOCAL = (
    r"(?:support|info|help|noreply|no-reply|admin|office|sales|hr|contact|press|"
    r"service|feedback|mail|hello|team|order)"
)
EMAIL_RE = re.compile(rf"(?<!\w)(?!{SERVICE_LOCAL}@)[\w.+-]+@[\w.-]+\.[\w-]+(?!\w)")
SERVICE_EMAIL_RE = re.compile(rf"(?<!\w){SERVICE_LOCAL}@[\w.-]+\.[\w-]+(?!\w)")

_AT = (
    r"(?:\s*\[at\]\s*|\s*\(at\)\s*|\s*\[собака\]\s*|\s*\(собака\)\s*"
    r"|\s+at\s+|\s+собака\s+)"
)
_DOT = (
    r"(?:\.|\s*\[dot\]\s*|\s*\(dot\)\s*|\s*\[точка\]\s*|\s*\(точка\)\s*"
    r"|\s+dot\s+|\s+точка\s+)"
)
OBFUSCATED_EMAIL_RE = re.compile(
    rf"(?<!\w)[a-zA-Z0-9._+-]+{_AT}[a-zA-Z0-9-]+(?:{_DOT}[a-zA-Z0-9-]+)*"
    rf"{_DOT}[a-zA-Z]{{2,10}}(?!\w)"
)

PHONE_PLUS7_RE = re.compile(
    r"(?<!\d)\+7[\s.\-]*\(?(?!800)\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"
)
PHONE_8_7_RE = re.compile(
    r"(?<!\d)[78][\s.\-]*\(?(?!800)\d{3}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)"
)
PHONE_NO_CODE_RE = re.compile(r"(?<!\d)\(?9\d{2}\)?[\s.\-]*\d{3}[\s.\-]*\d{2}[\s.\-]*\d{2}(?!\d)")
PHONE_INTL_RE = re.compile(
    r"(?<!\d)\+\d{1,3}[\s.\-]*\(?(?!800)\d{2,4}\)?[\s.\-]*\d{2,4}[\s.\-]*\d{2,4}[\s.\-]*\d{2,4}(?!\d)"
)

CARD_GROUPED_RE = re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)")
CARD_RUN_RE = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
CARD_RUN_16_RE = re.compile(r"(?<!\d)[2-6]\d{15}(?!\d)")
CARD_SPACED_RE = re.compile(r"(?<!\d)(?<![ -]\d)\d(?:[ -]\d){15,18}(?!\d)(?![ -]\d)")

INN_RUN_RE = re.compile(r"(?<!\d)(?:\d{10}|\d{12})(?!\d)")
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
EMAIL_ORG_CONTEXT = compile_keywords(
    [
        "отдел",
        "компании",
        "организации",
        "публичная",
        "общая",
        "служебная",
        "поддержки",
        "банка",
        "горячей линии",
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
        PatternRule(
            "CARD_NUMBER",
            CARD_SPACED_RE,
            0.35,
            validator=luhn_valid,
            validator_bonus=0.35,
            context=CARD_CONTEXT,
            context_bonus=0.3,
            negative=CARD_NEGATIVE,
            negative_penalty=0.4,
        ),
    )


def _inn_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "INN",
            INN_RUN_RE,
            0.2,
            validator=inn_valid,
            validator_bonus=0.25,
            context=INN_CONTEXT,
            context_bonus=0.45,
            context_window=30,
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


def _email_rules() -> Sequence[PatternRule]:
    return (
        PatternRule("EMAIL", EMAIL_RE, 0.95),
        PatternRule("EMAIL", OBFUSCATED_EMAIL_RE, 0.9),
        PatternRule(
            "EMAIL",
            SERVICE_EMAIL_RE,
            0.95,
            negative=EMAIL_ORG_CONTEXT,
            negative_penalty=0.5,
            context_window=40,
        ),
    )


def _cvv_pin_rules() -> Sequence[PatternRule]:
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


def _nearest_card_secret(doc: Document, start: int, end: int) -> str:
    """CVV или PIN — по ключевому слову, стоящему ближе к числу."""
    cvv_dist = find_keyword(doc, start, end, CVV_CONTEXT, 25, "before")
    pin_dists = [
        d
        for d in (
            find_keyword(doc, start, end, PIN_CONTEXT, 60, "before"),
            find_keyword(doc, start, end, PIN_CONTEXT, 15, "after"),
        )
        if d is not None
    ]
    if cvv_dist is not None and (not pin_dists or cvv_dist <= min(pin_dists)):
        return "CVV"
    return "PIN"


class CvvPinRecognizer(RegexRecognizer):
    """CVV и PIN одним распознавателем: для числа, найденного обоими правилами,
    остаётся тип ближайшего ключевого слова; из одинаковых — спан с наибольшим score."""

    def find(self, doc: Document) -> Iterable[Span]:
        by_pos: dict[tuple[int, int], list[Span]] = {}
        for span in super().find(doc):
            by_pos.setdefault((span.start, span.end), []).append(span)
        resolved: list[Span] = []
        for (start, end), group in by_pos.items():
            if {s.pii_type for s in group} == {"CVV", "PIN"}:
                winner = _nearest_card_secret(doc, start, end)
                group = [s for s in group if s.pii_type == winner]
            resolved.append(max(group, key=lambda s: s.score))
        return resolved


def recognizers() -> list[Recognizer]:
    return [
        RegexRecognizer("email", _email_rules()),
        RegexRecognizer("phone", _phone_rules()),
        RegexRecognizer("card", _card_rules()),
        RegexRecognizer("inn", _inn_rules()),
        CvvPinRecognizer("cvv_pin", _cvv_pin_rules()),
    ]
