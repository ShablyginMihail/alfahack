from __future__ import annotations

import re
from collections.abc import Iterable

from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.address import CITIES, COUNTRIES
from pii_guard.recognizers.names import get_morph

SETTLEMENT_MARKERS = r"(?:г\.|гор\.|город|с\.|село|пос\.|дер\.)"

BIRTH_PLACE_MARKERS = r"(?:место рождения|м\.р\.|м/р|уроженец|уроженка|уроженца)"
FIELD_MARKERS = r"(?:дата|паспорт|адрес|гражданство|телефон|снилс|инн|пол)"
BIRTH_PLACE_RE = re.compile(
    rf"(?<!\w){BIRTH_PLACE_MARKERS}\s*[:—]?\s*(.+?)(?=;|\n|,\s*(?:{FIELD_MARKERS})|$)"
)
_ABBREVIATIONS = frozenset(
    {"г", "гор", "обл", "с", "пос", "дер", "р-н", "респ", "пгт", "ст", "ул", "д", "корп", "кв"}
)

BORN_RE = re.compile(
    r"(?<!\w)(?:родился|родилась)\s+в\s+(?:городе\s+)?([а-яё]+(?:-[а-яё]+)*(?:\s+[а-яё]+(?:-[а-яё]+)*)?)(?!\w)"
)

CITIZENSHIP_MARKERS = r"(?:гражданство|гражданин|гражданка|подданство|citizenship)"

_country_names = sorted(COUNTRIES, key=len, reverse=True)
COUNTRY_PATTERN = "|".join(re.escape(name) + r"\w*" for name in _country_names)

CITIZENSHIP_RE = re.compile(rf"(?<!\w){CITIZENSHIP_MARKERS}\s*[:—\-]?\s*({COUNTRY_PATTERN})(?!\w)")
CITIZENSHIP_ADJ_RE = re.compile(rf"(?<!\w)({COUNTRY_PATTERN})\s+гражданство(?!\w)")

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
            raw = self._cut_period(match.group(1))
            stripped = re.sub(rf"^(?:{SETTLEMENT_MARKERS})\s*", "", raw)
            if len(stripped) > _MAX_BIRTH_PLACE:
                stripped = stripped[:_MAX_BIRTH_PLACE]
            if not stripped:
                continue
            idx = raw.find(stripped)
            start = match.start(1) + idx
            spans.append(Span(start, start + len(stripped), "BIRTH_PLACE", 0.9, self.name))
        return spans

    @staticmethod
    def _cut_period(value: str) -> str:
        for match in re.finditer(r"\.\s+", value):
            before = value[: match.start()]
            word = re.search(r"([а-яё0-9-]+)$", before)
            if word is None or (len(word.group(1)) > 3 and word.group(1) not in _ABBREVIATIONS):
                return before
        return value

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
        for match in CITIZENSHIP_ADJ_RE.finditer(doc.norm):
            spans.append(Span(match.start(1), match.end(1), "CITIZENSHIP", 0.9, self.name))
        return spans

    @staticmethod
    def _is_place(word: str) -> bool:
        normal = CivilRecognizer._normal_form(word)
        if normal in CITIES or normal in COUNTRIES:
            return True
        try:
            return any("Geox" in parse.tag for parse in get_morph().parse(word))
        except Exception:
            return False

    @staticmethod
    def _normal_form(word: str) -> str:
        try:
            return str(get_morph().parse(word)[0].normal_form)
        except Exception:
            return word


def recognizers() -> list[Recognizer]:
    return [CivilRecognizer()]
