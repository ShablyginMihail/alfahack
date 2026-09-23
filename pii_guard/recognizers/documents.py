from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.base import (
    FIELD_LABELS,
    OMS_WORDS,
    PatternRule,
    RegexRecognizer,
    cut_period,
)
from pii_guard.recognizers.validators import snils_valid

PASSPORT_WORD = "паспорт"

PASSPORT_COMBINED_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}[\s-]?(?:№\s*)?\d{6}(?!\d)")
PASSPORT_RUN_RE = re.compile(r"(?<!\d)\d{10}(?!\d)")

_SERIES_WORDS = r"(?:серия|серии|сер\.)"
_SERIES_GROUP = r"(\d{2}[\s-]?\d{2})"
_NO_SIX_DIGIT_NUMBER = r"(?![\s-]*(?:№\s*)?\d{6}(?!\d))"


def _series_re(document_word: str, series_group: str = _SERIES_GROUP) -> re.Pattern[str]:
    return re.compile(
        rf"(?<!\w){_SERIES_WORDS}\s*(?:{document_word}\s*)?[:№]?\s*{series_group}{_NO_SIX_DIGIT_NUMBER}(?!\d)"
    )


PASSPORT_SERIES_RE = _series_re("паспорта")
PASSPORT_NUMBER_RE = re.compile(r"(?<!\w)(?:номер|№)\s*(?:паспорта\s*)?[:.]?\s*(\d{6})(?!\d)")

DIVISION_CODE_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}(?![\s-]?\d)(?!\d)")

DRIVER_COMBINED_RE = re.compile(r"(?<!\d)\d{2}[\s-]?\d{2}[\s-]?\d{6}(?!\d)")
DRIVER_OLD_RE = re.compile(r"(?<!\d)\d{2}[\s-]?[А-Яа-яЁё]{2}[\s-]?\d{6}(?!\d)")
_DRIVER_SERIES_GROUP = r"(\d{2}[\s-]?\d{2}|\d{2}[\s-]?[А-Яа-я]{2})"
DRIVER_SERIES_RE = _series_re("удостоверения", _DRIVER_SERIES_GROUP)
DRIVER_NUMBER_RE = re.compile(r"(?<!\w)(?:номер|№)\s*(?:удостоверения\s*)?[:.]?\s*(\d{6})(?!\d)")

SNILS_GROUPED_RE = re.compile(r"(?<!\d)\d{3}[\s-]\d{3}[\s-]\d{3}[\s-]?\d{2}(?!\d)")
SNILS_RUN_RE = re.compile(r"(?<!\d)\d{11}(?!\d)")

FOREIGN_PASSPORT_RE = re.compile(r"(?<!\d)\d{2}[\s-]?(?:№|номер)?\s*\d{7}(?!\d)")

_CYR2 = r"[А-Яа-я]{2}"
_ROMAN = r"[IVXLCivxlc]+"

MILITARY_COMBINED_RE = re.compile(rf"(?<!\w){_CYR2}\s*(?:№\s*)?\d{{7}}(?!\d)")
MILITARY_SERIES_RE = re.compile(rf"(?<!\w){_SERIES_WORDS}\s*({_CYR2})(?!\w)")
MILITARY_NUMBER_RE = re.compile(r"(?<!\w)(?:номер|№)\s*(\d{7})(?!\d)")

BIRTH_COMBINED_RE = re.compile(rf"(?<!\w){_ROMAN}\s*-\s*{_CYR2}\s*(?:№\s*)?\d{{6}}(?!\d)")
BIRTH_SERIES_RE = re.compile(rf"(?<!\w){_SERIES_WORDS}\s*({_ROMAN}\s*-\s*{_CYR2})(?!\w)")
BIRTH_NUMBER_RE = re.compile(r"(?<!\w)(?:номер|№)\s*(\d{6})(?!\d)")

RESIDENCE_COMBINED_RE = re.compile(r"(?<!\d)\d{2}\s*(?:№\s*)?\d{7}(?!\d)")
RESIDENCE_NUMBER_RE = re.compile(r"(?<!\w)(?:№|номер)\s*(\d{6,7})(?!\d)")

FOREIGN_NATIONAL_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]{1,2}\s*\d{6,9}(?!\d)")

OMS_RUN_RE = re.compile(r"(?<!\d)\d{16}(?!\d)")
OMS_GROUPED_RE = re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)")

PASSPORT_CONTEXT = compile_keywords([PASSPORT_WORD, "серия", "серии", "номер паспорта", "пасп"])
PASSPORT_COMBINED_CONTEXT = compile_keywords(
    [PASSPORT_WORD, "серия", "серии", "номер паспорта", "пасп", "выдан"]
)
DIVISION_CONTEXT = compile_keywords(
    ["код подразделения", "подразделени", "код подр", "к/п", "к.п.", "кп"]
)
DIVISION_PASSPORT_CONTEXT = compile_keywords([PASSPORT_WORD, "выдан"])
_DRIVER_WORDS = ["водительск", "ву", "в/у", "права", "удостоверени", "удост", "вод. уд"]
DRIVER_CONTEXT = compile_keywords(_DRIVER_WORDS)
SNILS_CONTEXT = compile_keywords(["снилс", "страхов"])
FOREIGN_CONTEXT = compile_keywords(["загран", "заграничн"])

_MILITARY_WORDS = ["военный билет", "военного билета", "военник", "в/б", "воен. билет"]
_BIRTH_WORDS = ["свидетельство о рождении", "свидетельства о рождении", "св-во о рождении"]
_RESIDENCE_WORDS = [
    "вид на жительство",
    "вида на жительство",
    "внж",
    "разрешение на временное проживание",
    "рвп",
]
_FOREIGN_NATIONAL_WORDS = [
    "паспорт гражданина",
    "паспорт иностранного гражданина",
    "иностранный паспорт",
    "национальный паспорт",
    "паспорт республики",
    "national passport",
    "passport",
]

MILITARY_CONTEXT = compile_keywords(_MILITARY_WORDS)
BIRTH_CONTEXT = compile_keywords(_BIRTH_WORDS)
RESIDENCE_CONTEXT = compile_keywords(_RESIDENCE_WORDS)
FOREIGN_NATIONAL_CONTEXT = compile_keywords(_FOREIGN_NATIONAL_WORDS)
DOCUMENT_CONTEXT = compile_keywords(
    [*_DRIVER_WORDS, *_MILITARY_WORDS, *_BIRTH_WORDS, *_RESIDENCE_WORDS]
)

OMS_CONTEXT = compile_keywords(OMS_WORDS)

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
ISSUER_PASSPORT_CONTEXT = compile_keywords([PASSPORT_WORD])
_MAX_ISSUER = 150
_ISSUER_SCAN = 2 * _MAX_ISSUER
_ISSUER_FIELD_RE = re.compile(rf",\s*{FIELD_LABELS.pattern}")


def _passport_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "PASSPORT",
            PASSPORT_COMBINED_RE,
            0.45,
            context=PASSPORT_COMBINED_CONTEXT,
            context_bonus=0.45,
            negative=DOCUMENT_CONTEXT,
            negative_penalty=0.5,
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
            negative=DOCUMENT_CONTEXT,
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
            negative=DOCUMENT_CONTEXT,
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


def _military_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "MILITARY_ID",
            MILITARY_COMBINED_RE,
            0.15,
            context=MILITARY_CONTEXT,
            context_bonus=0.7,
            context_window=60,
        ),
        PatternRule(
            "MILITARY_ID",
            MILITARY_SERIES_RE,
            0.15,
            group=1,
            context=MILITARY_CONTEXT,
            context_bonus=0.7,
            context_window=60,
            part="series",
        ),
        PatternRule(
            "MILITARY_ID",
            MILITARY_NUMBER_RE,
            0.15,
            group=1,
            context=MILITARY_CONTEXT,
            context_bonus=0.7,
            context_window=60,
            part="number",
        ),
    )


def _birth_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "BIRTH_CERTIFICATE",
            BIRTH_COMBINED_RE,
            0.15,
            context=BIRTH_CONTEXT,
            context_bonus=0.7,
            context_window=60,
        ),
        PatternRule(
            "BIRTH_CERTIFICATE",
            BIRTH_SERIES_RE,
            0.15,
            group=1,
            context=BIRTH_CONTEXT,
            context_bonus=0.7,
            context_window=60,
            part="series",
        ),
        PatternRule(
            "BIRTH_CERTIFICATE",
            BIRTH_NUMBER_RE,
            0.15,
            group=1,
            context=BIRTH_CONTEXT,
            context_bonus=0.7,
            context_window=60,
            part="number",
        ),
    )


def _residence_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "RESIDENCE_PERMIT",
            RESIDENCE_COMBINED_RE,
            0.15,
            context=RESIDENCE_CONTEXT,
            context_bonus=0.7,
            context_window=60,
        ),
        PatternRule(
            "RESIDENCE_PERMIT",
            RESIDENCE_NUMBER_RE,
            0.15,
            group=1,
            context=RESIDENCE_CONTEXT,
            context_bonus=0.7,
            context_window=60,
            part="number",
        ),
    )


def _foreign_national_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "FOREIGN_NATIONAL_PASSPORT",
            FOREIGN_NATIONAL_RE,
            0.15,
            context=FOREIGN_NATIONAL_CONTEXT,
            context_bonus=0.7,
            context_window=60,
        ),
    )


def _oms_rules() -> Sequence[PatternRule]:
    return (
        PatternRule(
            "OMS_POLICY",
            OMS_RUN_RE,
            0.15,
            context=OMS_CONTEXT,
            context_bonus=0.8,
            context_window=60,
        ),
        PatternRule(
            "OMS_POLICY",
            OMS_GROUPED_RE,
            0.15,
            context=OMS_CONTEXT,
            context_bonus=0.8,
            context_window=60,
        ),
    )


def _extract_issuer_value(norm: str, start: int) -> str:
    limit = min(len(norm), start + _ISSUER_SCAN)
    candidates: list[int] = []
    for pattern in (ISSUER_DATE_RE, ISSUER_DIVISION_RE):
        match = pattern.search(norm, start, limit)
        if match is not None:
            candidates.append(match.start())
    for terminator in ISSUER_TERMINATORS:
        idx = norm.find(terminator, start, limit)
        if idx != -1:
            candidates.append(idx)
    for sep in (";", "\n"):
        idx = norm.find(sep, start, limit)
        if idx != -1:
            candidates.append(idx)
    field_match = _ISSUER_FIELD_RE.search(norm[start:limit])
    if field_match is not None:
        candidates.append(start + field_match.start())
    period = cut_period(norm[start:limit])
    if len(period) < limit - start:
        candidates.append(start + len(period))
    if not candidates:
        return norm[start:limit]
    return norm[start : min(candidates)]


class PassportIssuerRecognizer(Recognizer):
    name = "passport_issuer"
    pii_types = frozenset({"PASSPORT_ISSUER"})

    def find(self, doc: Document) -> Iterable[Span]:
        spans: list[Span] = []
        for match in ISSUER_RE.finditer(doc.norm):
            value = _extract_issuer_value(doc.norm, match.end())
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
        RegexRecognizer("military_id", _military_rules()),
        RegexRecognizer("birth_certificate", _birth_rules()),
        RegexRecognizer("residence_permit", _residence_rules()),
        RegexRecognizer("foreign_national_passport", _foreign_national_rules()),
        RegexRecognizer("oms_policy", _oms_rules()),
        PassportIssuerRecognizer(),
    ]
