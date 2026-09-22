from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.base import FIELD_LABELS, PatternRule, RegexRecognizer, cut_period
from pii_guard.recognizers.validators import snils_valid

PASSPORT_COMBINED_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}[\s-]?(?:№\s*)?\d{6}(?!\d)")
PASSPORT_RUN_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")
PASSPORT_SERIES_RE = re.compile(
    r"(?<!\w)(?:серия|серии|сер\.)\s*(?:паспорта\s*)?[:№]?\s*(\d{2}[\s-]?\d{2})(?![\s-]*(?:№\s*)?\d{6}(?!\d))(?!\d)"
)
PASSPORT_NUMBER_RE = re.compile(r"(?<!\w)(?:номер|№)\s*(?:паспорта\s*)?[:.]?\s*(\d{6})(?!\d)")

DIVISION_CODE_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}(?![\s-]?\d)(?!\d)")

DRIVER_COMBINED_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}[\s-]?\d{6}(?!\d)")
DRIVER_OLD_RE = re.compile(r"(?<!\d)\d{2}[\s-]?[А-Яа-яЁё]{2}[\s-]?\d{6}(?!\d)")
DRIVER_SERIES_RE = re.compile(
    r"(?<!\w)(?:серия|серии|сер\.)\s*(?:удостоверения\s*)?[:№]?\s*(\d{2}[\s-]?\d{2})(?![\s-]*(?:№\s*)?\d{6}(?!\d))(?!\d)"
)
DRIVER_NUMBER_RE = re.compile(r"(?<!\w)(?:номер|№)\s*(?:удостоверения\s*)?[:.]?\s*(\d{6})(?!\d)")

SNILS_GROUPED_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}[\s-]\d{3}[\s-]?\d{2}(?!\d)")
SNILS_RUN_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")

FOREIGN_PASSPORT_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{7}(?!\d)")

PASSPORT_CONTEXT = compile_keywords(["паспорт", "серия", "серии", "номер паспорта"])
DIVISION_CONTEXT = compile_keywords(["код подразделения", "подразделени", "код подр", "к/п"])
DIVISION_PASSPORT_CONTEXT = compile_keywords(["паспорт", "выдан"])
DRIVER_CONTEXT = compile_keywords(["водительск", "ву", "в/у", "права", "удостоверени"])
SNILS_CONTEXT = compile_keywords(["снилс", "страхов"])
FOREIGN_CONTEXT = compile_keywords(["загран", "заграничн"])

ISSUER_MARKERS = (
    r"(?:выдан|выдана|выдано|кем выдан|орган выдачи|выдавший орган|орган, выдавший паспорт)"
)
ORGAN_MARKERS = (
    r"(?:уфмс|оуфмс|фмс|увм|гувм|овм|мвд|увд|овд|ровд|оувд|гу|тп|"
    r"отдел|отделом|отделением|отделение|управление|управлением|паспортно-визов|пвс|милиции|полиции)"
)
ORGAN_WORD_RE = re.compile(rf"(?<!\w)(?:{ORGAN_MARKERS})(?!\w)")
ISSUER_RE = re.compile(rf"(?<!\w){ISSUER_MARKERS}\s*[:]?\s*")
ISSUER_DATE_RE = re.compile(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+[а-яё]+")
ISSUER_DIVISION_RE = re.compile(r"\d{3}-\d{3}")
ISSUER_TERMINATORS = ("код подразделения", "к/п", "дата выдачи")
ORGAN_PHRASE_RE = re.compile(rf"(?<!\w)({ORGAN_MARKERS}(?:\s+[а-яё0-9-]+){{1,6}})(?!\w)")
ISSUER_PASSPORT_CONTEXT = compile_keywords(["паспорт"])
_MAX_ISSUER = 150


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
            0.75,
            group=1,
            context=PASSPORT_CONTEXT,
            context_bonus=0.2,
            # «серия … номер …» после «водительское удостоверение» — это ВУ, а не паспорт
            negative=DRIVER_CONTEXT,
            negative_penalty=0.5,
            part="series",
        ),
        PatternRule(
            "PASSPORT",
            PASSPORT_NUMBER_RE,
            0.3,
            group=1,
            context=PASSPORT_CONTEXT,
            context_bonus=0.45,
            negative=DRIVER_CONTEXT,
            negative_penalty=0.5,
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
            context_direction="before",
        ),
        PatternRule(
            "DIVISION_CODE",
            DIVISION_CODE_RE,
            0.3,
            context=DIVISION_PASSPORT_CONTEXT,
            context_bonus=0.25,
            context_direction="before",
        ),
    )


def _driver_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_COMBINED_RE,
            0.2,
            context=DRIVER_CONTEXT,
            context_bonus=0.65,
        ),
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_OLD_RE,
            0.2,
            context=DRIVER_CONTEXT,
            context_bonus=0.65,
        ),
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_SERIES_RE,
            0.2,
            group=1,
            context=DRIVER_CONTEXT,
            context_bonus=0.5,
            part="series",
        ),
        PatternRule(
            "DRIVER_LICENSE",
            DRIVER_NUMBER_RE,
            0.2,
            group=1,
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


class PassportIssuerRecognizer(Recognizer):
    name = "passport_issuer"
    pii_types = frozenset({"PASSPORT_ISSUER"})

    def find(self, doc: Document) -> Iterable[Span]:
        spans: list[Span] = []
        for match in ISSUER_RE.finditer(doc.norm):
            value = self._extract_value(doc.norm, match.end())
            if not value or not self._has_organ_marker(value):
                continue
            value = value.rstrip(", \t\n")[:_MAX_ISSUER]
            if not value:
                continue
            spans.append(
                Span(match.end(), match.end() + len(value), "PASSPORT_ISSUER", 0.9, self.name)
            )
        for match in ORGAN_PHRASE_RE.finditer(doc.norm):
            if (
                find_keyword(doc, match.start(), match.end(), ISSUER_PASSPORT_CONTEXT, 60, "before")
                is None
            ):
                continue
            spans.append(Span(match.start(1), match.end(1), "PASSPORT_ISSUER", 0.75, self.name))
        return spans

    @staticmethod
    def _extract_value(norm: str, start: int) -> str:
        candidates: list[int] = []
        for pattern in (ISSUER_DATE_RE, ISSUER_DIVISION_RE):
            match = pattern.search(norm, start)
            if match is not None:
                candidates.append(match.start())
        for terminator in ISSUER_TERMINATORS:
            idx = norm.find(terminator, start)
            if idx != -1:
                candidates.append(idx)
        for sep in (";", "\n"):
            idx = norm.find(sep, start)
            if idx != -1:
                candidates.append(idx)
        field_match = re.search(rf",\s*{FIELD_LABELS.pattern}", norm[start:])
        if field_match is not None:
            candidates.append(start + field_match.start())
        period = cut_period(norm[start:])
        if len(period) < len(norm) - start:
            candidates.append(start + len(period))
        if not candidates:
            return norm[start:]
        return norm[start : min(candidates)]

    @staticmethod
    def _has_organ_marker(value: str) -> bool:
        first_words = " ".join(value.split()[:3])
        return ORGAN_WORD_RE.search(first_words) is not None


def recognizers() -> list[Recognizer]:
    return [
        RegexRecognizer("passport", _passport_rules()),
        RegexRecognizer("division_code", _division_rules()),
        RegexRecognizer("driver_license", _driver_rules()),
        RegexRecognizer("snils", _snils_rules()),
        RegexRecognizer("foreign_passport", _foreign_rules()),
        PassportIssuerRecognizer(),
    ]
