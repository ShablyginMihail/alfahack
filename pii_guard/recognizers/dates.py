from __future__ import annotations

import calendar
import re
from collections.abc import Iterable

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer

MONTH_PATTERN = (
    r"(?:январ|феврал|сентябр|октябр|ноябр|декабр|август|апрел|март|ма[йяе]|июн|июл|сен|"
    r"янв|февр|мар|апр|авг|сент|окт|нояб|дек)"
)

NUMERIC_DATE_RE = re.compile(r"(?<!\d)(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?!\d)")

MONTH_DATE_RE = re.compile(
    rf"(?<!\w)(?:в\s+)?((?:\d{{1,2}}(?:-го\s+|\s+))?{MONTH_PATTERN}(?:\.|\w*)\s+(\d{{4}}))(?!\d)"
)

ORDINAL_DAY = (
    r"(?:первое|первого|второе|второго|третье|третьего|четвертое|четвертого|"
    r"пятое|пятого|шестое|шестого|седьмое|седьмого|восьмое|восьмого|девятое|девятого|"
    r"одиннадцатое|одиннадцатого|двенадцатое|двенадцатого|тринадцатое|тринадцатого|"
    r"четырнадцатое|четырнадцатого|пятнадцатое|пятнадцатого|шестнадцатое|шестнадцатого|"
    r"семнадцатое|семнадцатого|восемнадцатое|восемнадцатого|девятнадцатое|девятнадцатого|"
    r"двадцатое|двадцатого|тридцатое|тридцатого|"
    r"двадцать\s+(?:первое|первого|второе|второго|третье|третьего|четвертое|четвертого|"
    r"пятое|пятого|шестое|шестого|седьмое|седьмого|восьмое|восьмого|девятое|девятого)|"
    r"тридцать\s+(?:первое|первого))"
)

_UNITS = (
    r"(?:один|одна|одного|одной|два|две|двух|три|трех|четыре|четырех|пять|пяти|шесть|шести|"
    r"семь|семи|восемь|восьми|девять|девяти)"
)
_TENS = (
    r"(?:десять|десяти|одиннадцать|одиннадцати|двенадцать|двенадцати|тринадцать|тринадцати|"
    r"четырнадцать|четырнадцати|пятнадцать|пятнадцати|шестнадцать|шестнадцати|семнадцать|семнадцати|"
    r"восемнадцать|восемнадцати|девятнадцать|девятнадцати|двадцать|двадцати|тридцать|тридцати|"
    r"сорок|сорока|пятьдесят|пятидесяти|шестьдесят|шестидесяти|семьдесят|семидесяти|"
    r"восемьдесят|восьмидесяти|девяносто|девяноста)"
)
_HUNDREDS = (
    r"(?:сто|ста|двести|двухсот|триста|трехсот|четыреста|четырехсот|пятьсот|пятисот|"
    r"шестьсот|шестисот|семьсот|семисот|восемьсот|восьмисот|девятьсот|девятисот)"
)
_THOUSANDS = r"(?:тысяча|тысячи|тысяч|две\s+тысячи)"
ORDINAL_YEAR = (
    r"(?:перв|втор|трет|четверт|пят|шест|седьм|восьм|девят|десят|"
    r"одиннадцат|двенадцат|тринадцат|четырнадцат|пятнадцат|шестнадцат|семнадцат|восемнадцат|девятнадцат|"
    r"двадцат|тридцат|сороков|пятидесят|шестидесят|семидесят|восьмидесят|девяност|"
    r"двухсот|трехсот|четырехсот|пятисот|шестисот|семисот|восьмисот|девятисот|сот|"
    r"двухтысячн|тысячн)(?:ого|ом|ый|ой|ье|ьего|ьем|ий)"
)
YEAR_WORDS = (
    rf"(?:{_THOUSANDS}\s+)?(?:{_HUNDREDS}\s+)?(?:{_TENS}\s+)?(?:{_UNITS}\s+)?{ORDINAL_YEAR}"
)

WORDS_DATE_RE = re.compile(
    rf"(?<!\w)(({ORDINAL_DAY})\s+{MONTH_PATTERN}(?:\.|\w*)\s+{YEAR_WORDS})\s+(?:года|год|году)(?!\w)"
)
YEAR_WORDS_ONLY_RE = re.compile(rf"(?<!\w)({YEAR_WORDS})\s+(?:году|года|год)(?!\w)")

BIRTH_CONTEXT = compile_keywords(
    ["дата рождения", "д.р.", "д/р", "родил", "рожден", "день рождения"]
)
BIRTH_GR_CONTEXT = compile_keywords(["г.р."])
ISSUE_CONTEXT = compile_keywords(["выдан", "дата выдачи", "выдачи", "когда выдан"])

_YEAR_MIN = 1920
_YEAR_MAX = 2012


def _valid(day: int, month: int, year: int) -> bool:
    if not (1 <= month <= 12):
        return False
    if len(str(year)) == 2:
        year4 = 2000 + year
    elif 1900 <= year <= 2099:
        year4 = year
    else:
        return False
    return 1 <= day <= calendar.monthrange(year4, month)[1]


def _numeric_year(a: int, b: int, c: int) -> int | None:
    if _valid(a, b, c):
        return c
    if _valid(c, b, a):
        return a
    return None


def _normalize_year(year: int) -> int:
    if len(str(year)) == 2:
        return 1900 + year
    return year


class DateRecognizer(Recognizer):
    name = "date"
    pii_types = frozenset({"BIRTH_DATE", "PASSPORT_ISSUE_DATE"})

    def find(self, doc: Document) -> Iterable[Span]:
        spans: list[Span] = []
        for match in NUMERIC_DATE_RE.finditer(doc.norm):
            year = _numeric_year(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            if year is None:
                continue
            span = self._classify(doc, match.start(), match.end(), year)
            if span is not None:
                spans.append(span)
        for match in MONTH_DATE_RE.finditer(doc.norm):
            year = int(match.group(2))
            span = self._classify(doc, match.start(1), match.end(1), year)
            if span is not None:
                spans.append(span)
        for match in WORDS_DATE_RE.finditer(doc.norm):
            span = self._classify_words(doc, match.start(1), match.end(1))
            if span is not None:
                spans.append(span)
        for match in YEAR_WORDS_ONLY_RE.finditer(doc.norm):
            span = self._classify_year_only(doc, match.start(1), match.end(1))
            if span is not None:
                spans.append(span)
        return spans

    def _classify(self, doc: Document, start: int, end: int, year: int) -> Span | None:
        if (
            find_keyword(doc, start, end, BIRTH_CONTEXT, 40, "before") is not None
            or find_keyword(doc, start, end, BIRTH_CONTEXT, 20, "after") is not None
            or find_keyword(doc, start, end, BIRTH_GR_CONTEXT, 40, "both") is not None
        ):
            return Span(start, end, "BIRTH_DATE", 0.9, self.name)
        if find_keyword(doc, start, end, ISSUE_CONTEXT, 40, "before") is not None:
            return Span(start, end, "PASSPORT_ISSUE_DATE", 0.9, self.name)
        normalized = _normalize_year(year)
        if _YEAR_MIN <= normalized <= _YEAR_MAX:
            return Span(start, end, "BIRTH_DATE", 0.4, self.name)
        return None

    def _classify_words(self, doc: Document, start: int, end: int) -> Span | None:
        if (
            find_keyword(doc, start, end, BIRTH_CONTEXT, 40, "before") is not None
            or find_keyword(doc, start, end, BIRTH_CONTEXT, 20, "after") is not None
            or find_keyword(doc, start, end, BIRTH_GR_CONTEXT, 40, "both") is not None
        ):
            return Span(start, end, "BIRTH_DATE", 0.9, self.name)
        if find_keyword(doc, start, end, ISSUE_CONTEXT, 40, "before") is not None:
            return Span(start, end, "PASSPORT_ISSUE_DATE", 0.9, self.name)
        return None

    def _classify_year_only(self, doc: Document, start: int, end: int) -> Span | None:
        if (
            find_keyword(doc, start, end, BIRTH_CONTEXT, 40, "before") is not None
            or find_keyword(doc, start, end, BIRTH_CONTEXT, 20, "after") is not None
            or find_keyword(doc, start, end, BIRTH_GR_CONTEXT, 40, "both") is not None
        ):
            return Span(start, end, "BIRTH_DATE", 0.9, self.name)
        return None


def recognizers() -> list[Recognizer]:
    return [DateRecognizer()]
