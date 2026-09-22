from __future__ import annotations

import calendar
import re
from collections.abc import Iterable

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.names import public_figure_context

MONTH_PATTERN = (
    r"(?:январ|феврал|сентябр|октябр|ноябр|декабр|август|апрел|март|ма[йяе]|июн|июл|сен|"
    r"янв|февр|мар|апр|авг|сент|окт|нояб|дек)"
)

NUMERIC_DATE_RE = re.compile(r"(?<!\d)(\d{1,4})[./-](\d{1,2})[./-](\d{1,4})(?!\d)")

ORDINAL_DAY = (
    r"(?:первое|первого|второе|второго|третье|третьего|четвертое|четвертого|"
    r"пятое|пятого|шестое|шестого|седьмое|седьмого|восьмое|восьмого|девятое|девятого|"
    r"десятое|десятого|"
    r"одиннадцатое|одиннадцатого|двенадцатое|двенадцатого|тринадцатое|тринадцатого|"
    r"четырнадцатое|четырнадцатого|пятнадцатое|пятнадцатого|шестнадцатое|шестнадцатого|"
    r"семнадцатое|семнадцатого|восемнадцатое|восемнадцатого|девятнадцатое|девятнадцатого|"
    r"двадцатое|двадцатого|тридцатое|тридцатого|"
    r"двадцать\s+(?:первое|первого|второе|второго|третье|третьего|четвертое|четвертого|"
    r"пятое|пятого|шестое|шестого|седьмое|седьмого|восьмое|восьмого|девятое|девятого)|"
    r"тридцать\s+(?:первое|первого))"
)

MONTH_DATE_RE = re.compile(
    rf"(?<!\w)(?:в\s+)?((?:{ORDINAL_DAY}\s+|(?:\d{{1,2}}(?:-го\s+|\s+)))?{MONTH_PATTERN}(?:\.|\w*)\s+(\d{{4}}))(?!\d)"
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
    rf"(?<!\w)(({ORDINAL_DAY})\s+{MONTH_PATTERN}(?:\.|\w*)\s+{YEAR_WORDS})(?:\s+(?:года|год|году|г\.|г))?(?!\w)"
)
YEAR_WORDS_ONLY_RE = re.compile(rf"(?<!\w)({YEAR_WORDS})\s+(?:году|года|год|г\.|г)(?!\w)")
YEAR_GR_RE = re.compile(r"(?<!\d)(\d{4})\s*(?:г\.\s*р\.|года\s+рождения)(?!\w)")
YEAR_NUMERIC_RE = re.compile(r"(?<!\d)(\d{4})\s+(?:году|года|г\.)(?!\w)")
YEAR_AFTER_GR_RE = re.compile(r"(?<!\w)(?:г\.\s*р\.|год\s+рождения)\s*[:]?\s*(\d{4})(?!\d)")

BIRTH_CONTEXT = compile_keywords(
    [
        "дата рождения",
        "дата рожд",
        "д.р.",
        "д. р.",
        "д/р",
        "др",
        "родил",
        "рожден",
        "день рождения",
        "год рождения",
        "г. р.",
    ]
)
BIRTH_GR_CONTEXT = compile_keywords(["г.р."])
ISSUE_CONTEXT = compile_keywords(
    [
        "выдан",
        "дата выдачи",
        "выдачи",
        "когда выдан",
        "паспорт получен",
        "паспорт получила",
        "паспорт получил",
        "получен паспорт",
        "дата получения",
    ]
)

_YEAR_MIN = 1920
_YEAR_MAX = 2012


def _valid(day: int, month: int, year: int, year_len: int) -> bool:
    if not (1 <= month <= 12):
        return False
    if year_len == 2:
        year4 = 2000 + year
    elif 1900 <= year <= 2099:
        year4 = year
    else:
        return False
    return 1 <= day <= calendar.monthrange(year4, month)[1]


def _numeric_year(a_str: str, b_str: str, c_str: str) -> int | None:
    a, b, c = int(a_str), int(b_str), int(c_str)
    if _valid(a, b, c, len(c_str)):
        return c
    if _valid(c, b, a, len(a_str)):
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
            year = _numeric_year(match.group(1), match.group(2), match.group(3))
            if year is None:
                continue
            self._collect(spans, self._classify(doc, match.start(), match.end(), year))
        for match in MONTH_DATE_RE.finditer(doc.norm):
            year = int(match.group(2))
            self._collect(spans, self._classify(doc, match.start(1), match.end(1), year))
        for match in WORDS_DATE_RE.finditer(doc.norm):
            self._collect(spans, self._classify_words(doc, match.start(1), match.end(1)))
        for match in YEAR_WORDS_ONLY_RE.finditer(doc.norm):
            self._collect(spans, self._classify_year_only(doc, match.start(1), match.end(1)))
        for match in YEAR_GR_RE.finditer(doc.norm):
            # маркер «г.р.» входит в само совпадение, контекст искать не нужно
            spans.append(Span(match.start(1), match.end(1), "BIRTH_DATE", 0.9, self.name))
        for match in YEAR_AFTER_GR_RE.finditer(doc.norm):
            spans.append(Span(match.start(1), match.end(1), "BIRTH_DATE", 0.9, self.name))
        for match in YEAR_NUMERIC_RE.finditer(doc.norm):
            self._collect(spans, self._classify_year_only(doc, match.start(1), match.end(1)))
        return spans

    @staticmethod
    def _collect(spans: list[Span], span: Span | None) -> None:
        if span is not None:
            spans.append(span)

    def _context_type(self, doc: Document, start: int, end: int) -> str | None:
        birth_before = find_keyword(doc, start, end, BIRTH_CONTEXT, 40, "before")
        birth_gr = find_keyword(doc, start, end, BIRTH_GR_CONTEXT, 40, "both")
        issue = find_keyword(doc, start, end, ISSUE_CONTEXT, 40, "before")
        pii_type: str | None = None
        if birth_before is not None or birth_gr is not None or issue is not None:
            candidates: list[tuple[int, str]] = []
            if birth_before is not None:
                candidates.append((birth_before, "BIRTH_DATE"))
            if birth_gr is not None:
                candidates.append((birth_gr, "BIRTH_DATE"))
            if issue is not None:
                candidates.append((issue, "PASSPORT_ISSUE_DATE"))
            pii_type = min(candidates, key=lambda item: item[0])[1]
        elif find_keyword(doc, start, end, BIRTH_CONTEXT, 20, "after") is not None:
            pii_type = "BIRTH_DATE"
        if pii_type == "BIRTH_DATE" and public_figure_context(doc, start):
            return None
        return pii_type

    def _classify(self, doc: Document, start: int, end: int, year: int) -> Span | None:
        pii_type = self._context_type(doc, start, end)
        if pii_type is not None:
            return Span(start, end, pii_type, 0.9, self.name)
        normalized = _normalize_year(year)
        if _YEAR_MIN <= normalized <= _YEAR_MAX:
            if public_figure_context(doc, start):
                return None
            return Span(start, end, "BIRTH_DATE", 0.4, self.name)
        return None

    def _classify_words(self, doc: Document, start: int, end: int) -> Span | None:
        pii_type = self._context_type(doc, start, end)
        if pii_type is not None:
            return Span(start, end, pii_type, 0.9, self.name)
        if public_figure_context(doc, start):
            return None
        return Span(start, end, "BIRTH_DATE", 0.4, self.name)

    def _classify_year_only(self, doc: Document, start: int, end: int) -> Span | None:
        pii_type = self._context_type(doc, start, end)
        if pii_type is not None:
            return Span(start, end, pii_type, 0.9, self.name)
        if public_figure_context(doc, start):
            return None
        return Span(start, end, "BIRTH_DATE", 0.4, self.name)


def recognizers() -> list[Recognizer]:
    return [DateRecognizer()]
