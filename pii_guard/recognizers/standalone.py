from __future__ import annotations

import calendar
import re
from collections.abc import Callable, Iterable

from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.address import CITIES, COUNTRIES
from pii_guard.recognizers.dates import MONTH_PATTERN, NUMERIC_DATE_RE
from pii_guard.recognizers.documents import ORGAN_WORD_RE
from pii_guard.recognizers.names import parse_word
from pii_guard.recognizers.validators import digits, inn_valid

_MAX_REGION = 120

_DIGIT_REGION_RE = re.compile(r"\+?\d[\d\s().\/-]*")
_DIVISION_FORM_RE = re.compile(r"\d{3}[- ]\d{3}")
_SNILS_FORM_RE = re.compile(r"\d{3}-\d{3}-\d{3} \d{2}")
_MONTH_DATE_STANDALONE_RE = re.compile(
    rf"(\d{{1,2}})\s+{MONTH_PATTERN}(?:\.|\w*)\s+(\d{{4}})(?:\s+(?:года|год|г\.|г))?"
)
_YEAR_BIRTH_RE = re.compile(r"(\d{4})\s*(?:г\.\s*р\.|года\s+рождения)")
_SETTLEMENT_MARKER_RE = re.compile(r"^(?:г\.|гор\.|город|с\.|село|пос\.|п\.|дер\.|деревня|пгт)\s*")
_WORD_RE = re.compile(r"[а-яё]+(?:-[а-яё]+)*")
_DEPARTMENT_RE = re.compile(r"фмс|мвд|овд|увд")


def _valid_date(day: int, month: int, year: int) -> bool:
    if not (1 <= month <= 12):
        return False
    if len(str(year)) == 2:
        year4 = 2000 + year
    elif 1900 <= year <= 2030:
        year4 = year
    else:
        return False
    return 1 <= day <= calendar.monthrange(year4, month)[1]


def _has_geox(word: str) -> bool:
    return any("Geox" in parse.tag for parse in parse_word(word))


def _has_person_tag(word: str) -> bool:
    return any(
        any(tag in parse.tag for tag in ("Surn", "Name", "Patr")) for parse in parse_word(word)
    )


def _full(pii_type: str) -> Callable[[str], tuple[str, int, int]]:
    def handler(region: str) -> tuple[str, int, int]:
        return pii_type, 0, len(region)

    return handler


def _division(region: str) -> tuple[str, int, int]:
    if _DIVISION_FORM_RE.fullmatch(region):
        return "DIVISION_CODE", 0, len(region)
    return "PASSPORT", 0, len(region)


def _inn_or_passport(region: str) -> tuple[str, int, int]:
    if region.isdigit() and inn_valid(region):
        return "INN", 0, len(region)
    return "PASSPORT", 0, len(region)


def _snils_or_phone(region: str) -> tuple[str, int, int]:
    if _SNILS_FORM_RE.fullmatch(region):
        return "SNILS", 0, len(region)
    return "PHONE", 0, len(region)


_DIGIT_HANDLERS: dict[int, Callable[[str], tuple[str, int, int]]] = {
    3: _full("CVV"),
    4: _full("PIN"),
    6: _division,
    10: _inn_or_passport,
    11: _snils_or_phone,
    12: _full("INN"),
    13: _full("CARD_NUMBER"),
    14: _full("CARD_NUMBER"),
    15: _full("CARD_NUMBER"),
    16: _full("CARD_NUMBER"),
    17: _full("CARD_NUMBER"),
    18: _full("CARD_NUMBER"),
    19: _full("CARD_NUMBER"),
}


class StandaloneValueRecognizer(Recognizer):
    name = "standalone"
    pii_types = frozenset(
        {
            "BIRTH_DATE",
            "CVV",
            "PIN",
            "DIVISION_CODE",
            "PASSPORT",
            "INN",
            "SNILS",
            "PHONE",
            "CARD_NUMBER",
            "PASSPORT_ISSUER",
            "CITIZENSHIP",
            "ADDRESS",
            "PERSON",
        }
    )

    def find(self, doc: Document) -> Iterable[Span]:
        start, end = self._region(doc)
        if end - start > _MAX_REGION:
            return []
        region = doc.norm[start:end]
        if not region:
            return []

        result = self._match(region)
        if result is None:
            return []
        pii_type, span_start, span_end = result
        return [Span(start + span_start, start + span_end, pii_type, 0.6, self.name)]

    @staticmethod
    def _region(doc: Document) -> tuple[int, int]:
        text = doc.text
        start = 0
        end = len(text)
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        while end > start and text[end - 1] in ",;:!?":
            end -= 1
        return start, end

    def _match(self, region: str) -> tuple[str, int, int] | None:
        if _DIGIT_REGION_RE.fullmatch(region):
            return self._match_digits(region)
        month_date = _MONTH_DATE_STANDALONE_RE.fullmatch(region)
        if month_date is not None:
            day = int(month_date.group(1))
            if 1 <= day <= 31:
                return "BIRTH_DATE", month_date.start(1), month_date.end(2)
        year_birth = _YEAR_BIRTH_RE.fullmatch(region)
        if year_birth is not None:
            return "BIRTH_DATE", year_birth.start(1), year_birth.end(1)
        issuer = self._match_issuer(region)
        if issuer is not None:
            return issuer
        country = self._match_country(region)
        if country is not None:
            return country
        settlement = self._match_settlement(region)
        if settlement is not None:
            return settlement
        if _WORD_RE.fullmatch(region) and _has_person_tag(region):
            return "PERSON", 0, len(region)
        return None

    @staticmethod
    def _match_issuer(region: str) -> tuple[str, int, int] | None:
        if (
            ORGAN_WORD_RE.match(region)
            and len(region.split()) <= 25
            and _DEPARTMENT_RE.search(region) is not None
        ):
            return "PASSPORT_ISSUER", 0, len(region)
        return None

    @staticmethod
    def _match_country(region: str) -> tuple[str, int, int] | None:
        norm_region = region.lower().replace("ё", "е")
        if norm_region in COUNTRIES or norm_region in ("рф", "российская федерация"):
            return "CITIZENSHIP", 0, len(region)
        return None

    def _match_digits(self, region: str) -> tuple[str, int, int] | None:
        date = NUMERIC_DATE_RE.fullmatch(region)
        if date is not None:
            a, b, c = int(date.group(1)), int(date.group(2)), int(date.group(3))
            if _valid_date(a, b, c) or _valid_date(c, b, a):
                return "BIRTH_DATE", 0, len(region)
        n = len(digits(region))
        handler = _DIGIT_HANDLERS.get(n)
        if handler is None:
            return None
        return handler(region)

    def _match_settlement(self, region: str) -> tuple[str, int, int] | None:
        marker = _SETTLEMENT_MARKER_RE.match(region)
        name_start = marker.end() if marker is not None else 0
        name = region[name_start:]
        words = name.split()
        if 1 <= len(words) <= 3 and all(w in CITIES for w in words):
            return "ADDRESS", name_start, len(region)
        if len(words) == 1 and _has_geox(words[0]):
            return "ADDRESS", name_start, len(region)
        return None


def recognizers() -> list[Recognizer]:
    return [StandaloneValueRecognizer()]
