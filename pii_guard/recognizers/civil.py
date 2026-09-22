from __future__ import annotations

import re
from collections.abc import Iterable

from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.address import CITIES, COUNTRIES
from pii_guard.recognizers.base import cut_period
from pii_guard.recognizers.names import parse_word

SETTLEMENT_MARKERS = r"(?:г\.|гор\.|город|с\.|село|пос\.|дер\.)"
PLACE_MARKERS = r"(?:г\.|гор\.|город|с\.|село|пос\.|дер\.|обл\.|область|р-н|район|край|республика)"

BIRTH_PLACE_MARKERS = r"(?:место рождения|м\.р\.|м/р|уроженец|уроженка|уроженца)"
BIRTH_PLACE_RE = re.compile(
    rf"(?<!\w){BIRTH_PLACE_MARKERS}\s*[:-]?\s*(.+?)(?=;|\n|,\s*(?!{PLACE_MARKERS})|$)"
)

BORN_RE = re.compile(
    r"(?<!\w)(?:родился|родилась)\s+в\s+(?:городе\s+)?([а-яё]+(?:-[а-яё]+)*(?:\s+[а-яё]+(?:-[а-яё]+)*)?)(?!\w)"
)

CITIZENSHIP_MARKERS = r"(?:гражданство|гражданин|гражданка|подданство|citizenship)"

_country_names = sorted(COUNTRIES, key=len, reverse=True)
COUNTRY_PATTERN = "|".join(re.escape(name) + r"\w*" for name in _country_names)

CITIZENSHIP_RE = re.compile(rf"(?<!\w){CITIZENSHIP_MARKERS}\s*[:-]?\s*({COUNTRY_PATTERN})(?!\w)")
CITIZENSHIP_ADJ_RE = re.compile(rf"(?<!\w)({COUNTRY_PATTERN})\s+гражданство(?!\w)")
CITIZENSHIP_FIRST_WORD_RE = re.compile(
    rf"(?<!\w){CITIZENSHIP_MARKERS}\s*[:-]?\s*([а-яё]+(?:-[а-яё]+)*)"
)

_MAX_BIRTH_PLACE = 80


class CivilRecognizer(Recognizer):
    name = "civil"
    pii_types = frozenset({"BIRTH_PLACE", "CITIZENSHIP"})

    def find(self, doc: Document) -> Iterable[Span]:
        spans: list[Span] = []
        spans.extend(self._birth_places(doc))
        spans.extend(self._born_places(doc))
        spans.extend(self._citizenships(doc))
        return spans

    def _birth_places(self, doc: Document) -> list[Span]:
        spans: list[Span] = []
        for match in BIRTH_PLACE_RE.finditer(doc.norm):
            raw = cut_period(match.group(1))
            stripped = re.sub(rf"^(?:{SETTLEMENT_MARKERS})\s*", "", raw)
            if len(stripped) > _MAX_BIRTH_PLACE:
                stripped = stripped[:_MAX_BIRTH_PLACE]
            if not stripped:
                continue
            idx = raw.find(stripped)
            start = match.start(1) + idx
            spans.append(Span(start, start + len(stripped), "BIRTH_PLACE", 0.9, self.name))
        return spans

    def _born_places(self, doc: Document) -> list[Span]:
        spans: list[Span] = []
        for match in BORN_RE.finditer(doc.norm):
            place = match.group(1)
            if not self._is_place(place):
                continue
            spans.append(Span(match.start(1), match.end(1), "BIRTH_PLACE", 0.8, self.name))
        return spans

    def _citizenships(self, doc: Document) -> list[Span]:
        spans: list[Span] = []
        for match in CITIZENSHIP_RE.finditer(doc.norm):
            spans.append(Span(match.start(1), match.end(1), "CITIZENSHIP", 0.9, self.name))
        for match in CITIZENSHIP_FIRST_WORD_RE.finditer(doc.norm):
            if self._normal_form(match.group(1)) in COUNTRIES:
                spans.append(Span(match.start(1), match.end(1), "CITIZENSHIP", 0.9, self.name))
        for match in CITIZENSHIP_ADJ_RE.finditer(doc.norm):
            spans.append(Span(match.start(1), match.end(1), "CITIZENSHIP", 0.9, self.name))
        return spans

    @staticmethod
    def _is_place(word: str) -> bool:
        normal = CivilRecognizer._normal_form(word)
        if normal in CITIES or normal in COUNTRIES:
            return True
        try:
            return any("Geox" in parse.tag for parse in parse_word(word))
        except Exception:
            return False

    @staticmethod
    def _normal_form(word: str) -> str:
        try:
            return str(parse_word(word)[0].normal_form)
        except Exception:
            return word


def recognizers() -> list[Recognizer]:
    return [CivilRecognizer()]
