from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.recognizers.names import FUNCTION_WORDS, parse_word

POSTAL_CODE_RE = re.compile(r"(?<!\d)[1-6]\d{5}(?!\d)")

CITY_MARKERS = (
    r"(?:г\.|гор\.|город|города|городе|пос\.|поселок|поселке|с\.|село|селе"
    r"|дер\.|деревня|деревне|пгт|ст-ца|станица)"
)
CITY_RE = re.compile(
    rf"(?<!\w){CITY_MARKERS}\s*[:.]?\s*([а-яё]+(?:-[а-яё]+)*(?:\s+[а-яё]+(?:-[а-яё]+)*)?)(?!\w)"
)

STREET_MARKERS = (
    r"(?:ул\.|улица|улицы|улице|улицу|улицей|пр-т|пр\.|проспект|проспекта|проспекте|"
    r"пер\.|переулок|переулка|переулке|ш\.|шоссе|б-р|бульвар|бульваре|наб\.|набережная|набережной|"
    r"пл\.|площадь|площади|проезд|проезде|туп\.|тупик|аллея|мкр|микрорайон)"
)
_STREET_WORD = r"[а-яё0-9]+(?:-[а-яё0-9]+)*"
STREET_RE = re.compile(
    rf"(?<!\w){STREET_MARKERS}\s*[:.]?\s*({_STREET_WORD}(?:\s+{_STREET_WORD}){{0,2}})(?!\w)"
)
STREET_AFTER_MARKERS = (
    r"(?:проспект|пр-т|улица|шоссе|бульвар|б-р|переулок|проезд|набережная|тупик|аллея)"
)
STREET_AFTER_RE = re.compile(
    rf"(?<!\w)({_STREET_WORD}(?:\s+{_STREET_WORD})?)\s*{STREET_AFTER_MARKERS}(?!\w)"
)

REGION_RE = re.compile(r"(?<!\w)([а-яё]+(?:-[а-яё]+)*)\s+(?:обл\.|область|край)(?!\w)")
REGION_REPUBLIC_RE = re.compile(r"(?<!\w)республик\w*\s+([а-яё]+(?:-[а-яё]+)*)(?!\w)")
REGION_AO_RE = re.compile(r"(?<!\w)([а-яё]+(?:-[а-яё]+)*)\s+(?:АО|автономный\s+округ)(?!\w)")

HOUSE_RE = re.compile(
    r"(?<!\w)(?:д\.|дом|дома|доме)\s*[:.]?\s*(\d+(?:[/-]\d+)?(?:[а-яё]\d*)?)(?!\w)"
)
CORPS_RE = re.compile(r"(?<!\w)(?:корп\.|к\.|стр\.|строение|лит\.)\s*[:.]?\s*(\d+[а-яё]?)(?!\w)")
APARTMENT_RE = re.compile(
    r"(?<!\w)(?:кв\.|квартира|квартиры|квартире|оф\.|офис|пом\.|помещение)\s*[:.]?\s*(\d+[а-яё]?)(?!\w)"
)

WORD_RE = re.compile(r"[а-яё]+(?:-[а-яё]+)*")

STREET_STOP_WORDS = frozenset(
    {"банкомат", "отделение", "офис", "филиал", "дом", "здание", "магазин", "центр"}
)
_ADJECTIVE_END = re.compile(r"(?:ий|ый|ой|ая|яя|ое|ее)$")

ADDRESS_CONTEXT = compile_keywords(
    [
        "проживает",
        "прожива",
        "прописан",
        "зарегистрирован",
        "адрес",
        "живу",
        "доставк",
        "клиент",
        "из города",
    ]
)
BANK_CONTEXT = compile_keywords(
    [
        "отделени",
        "офис банка",
        "филиал",
        "банкомат",
        "терминал",
        "дополнительный офис",
        "центр обслуживания",
        "наш офис",
        "мы находимся",
    ]
)
BANK_EXCEPTION = compile_keywords(
    [
        "проживает",
        "прописан",
        "зарегистрирован",
        "адрес регистрации",
        "адрес проживания",
        "мой адрес",
        "клиент",
    ]
)


def _load_words(filename: str) -> frozenset[str]:
    path = Path(__file__).resolve().parent.parent.parent / "data" / "dicts" / filename
    if not path.exists():
        return frozenset()
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


COUNTRIES = _load_words("countries.txt")
CITIES = _load_words("cities.txt")

_country_names = sorted(COUNTRIES, key=len, reverse=True)
COUNTRY_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(re.escape(name) + r"\w*" for name in _country_names) + r")(?!\w)"
)


@dataclass(slots=True)
class _Component:
    start: int
    end: int
    full_start: int
    full_end: int
    part: str


class AddressRecognizer(Recognizer):
    name = "address"
    pii_types = frozenset({"ADDRESS"})

    def find(self, doc: Document) -> Iterable[Span]:
        components = self._find_components(doc)
        spans: list[Span] = []
        for chain in self._group_chains(doc, components):
            if self._is_bank_branch(doc, chain[0].full_start):
                continue
            if len(chain) >= 2:
                for comp in chain:
                    spans.append(
                        Span(comp.start, comp.end, "ADDRESS", 0.85, self.name, part=comp.part)
                    )
            else:
                comp = chain[0]
                score = self._single_score(doc, comp)
                spans.append(
                    Span(comp.start, comp.end, "ADDRESS", score, self.name, part=comp.part)
                )
        for city in self._find_cities_without_marker(doc):
            if self._is_bank_branch(doc, city.full_start):
                continue
            spans.append(Span(city.start, city.end, "ADDRESS", 0.7, self.name, part="city"))
        return spans

    def _find_components(self, doc: Document) -> list[_Component]:
        components: list[_Component] = []
        components.extend(self._postal_codes(doc))
        components.extend(self._cities(doc))
        components.extend(self._streets(doc))
        components.extend(self._regions(doc))
        components.extend(self._houses(doc))
        components.extend(self._apartments(doc))
        components.extend(self._countries(doc))
        return components

    @staticmethod
    def _postal_codes(doc: Document) -> list[_Component]:
        return [
            _Component(m.start(), m.end(), m.start(), m.end(), "postal_code")
            for m in POSTAL_CODE_RE.finditer(doc.norm)
        ]

    @staticmethod
    def _cities(doc: Document) -> list[_Component]:
        return [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "city")
            for m in CITY_RE.finditer(doc.norm)
        ]

    @staticmethod
    def _streets(doc: Document) -> list[_Component]:
        components = [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "street")
            for m in STREET_RE.finditer(doc.norm)
        ]
        components.extend(
            _Component(m.start(1), m.end(1), m.start(), m.end(), "street")
            for m in STREET_AFTER_RE.finditer(doc.norm)
            if AddressRecognizer._valid_street_after(m.group(1))
        )
        return components

    @staticmethod
    def _valid_street_after(name: str) -> bool:
        words = [w for w in name.split() if w]
        if not words or len(words) > 2:
            return False
        if any(w in FUNCTION_WORDS or w in STREET_STOP_WORDS for w in words):
            return False
        return any(AddressRecognizer._is_adjective(w) for w in words)

    @staticmethod
    def _is_adjective(word: str) -> bool:
        if _ADJECTIVE_END.search(word):
            return True
        try:
            return any("ADJF" in parse.tag for parse in parse_word(word))
        except Exception:
            return False

    @staticmethod
    def _regions(doc: Document) -> list[_Component]:
        components = [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "region")
            for m in REGION_RE.finditer(doc.norm)
        ]
        components.extend(
            _Component(m.start(1), m.end(1), m.start(), m.end(), "region")
            for m in REGION_REPUBLIC_RE.finditer(doc.norm)
        )
        components.extend(
            _Component(m.start(1), m.end(1), m.start(), m.end(), "region")
            for m in REGION_AO_RE.finditer(doc.norm)
        )
        return components

    @staticmethod
    def _houses(doc: Document) -> list[_Component]:
        components = [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "house")
            for m in HOUSE_RE.finditer(doc.norm)
        ]
        components.extend(
            _Component(m.start(1), m.end(1), m.start(), m.end(), "house")
            for m in CORPS_RE.finditer(doc.norm)
        )
        return components

    @staticmethod
    def _apartments(doc: Document) -> list[_Component]:
        return [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "apartment")
            for m in APARTMENT_RE.finditer(doc.norm)
        ]

    @staticmethod
    def _countries(doc: Document) -> list[_Component]:
        return [
            _Component(m.start(), m.end(), m.start(), m.end(), "country")
            for m in COUNTRY_RE.finditer(doc.norm)
        ]

    @staticmethod
    def _group_chains(doc: Document, components: list[_Component]) -> list[list[_Component]]:
        ordered = sorted(components, key=lambda c: c.full_start)
        chains: list[list[_Component]] = []
        current: list[_Component] = []
        for comp in ordered:
            if current and not all(
                ch in ", \t\n" for ch in doc.norm[current[-1].full_end : comp.full_start]
            ):
                chains.append(current)
                current = []
            current.append(comp)
        if current:
            chains.append(current)
        return chains

    def _single_score(self, doc: Document, comp: _Component) -> float:
        if comp.part == "postal_code" and self._has_index_marker(doc, comp.start):
            return 0.75
        if find_keyword(doc, comp.start, comp.end, ADDRESS_CONTEXT, 40, "before") is not None:
            return 0.75
        return 0.45

    @staticmethod
    def _has_index_marker(doc: Document, start: int) -> bool:
        before = doc.norm[max(0, start - 20) : start]
        return re.search(r"(?:почтовый\s+)?индекс\s*:?\s*$", before) is not None

    def _is_bank_branch(self, doc: Document, start: int) -> bool:
        if find_keyword(doc, start, start, BANK_CONTEXT, 60, "before") is None:
            return False
        return find_keyword(doc, start, start, BANK_EXCEPTION, 60, "before") is None

    def _find_cities_without_marker(self, doc: Document) -> list[_Component]:
        cities: list[_Component] = []
        for match in WORD_RE.finditer(doc.norm):
            # сначала дешёвая проверка контекста, морфология — только для кандидатов
            if find_keyword(doc, match.start(), match.end(), ADDRESS_CONTEXT, 40, "before") is None:
                continue
            if self._city_normal(match.group(0)) not in CITIES:
                continue
            cities.append(
                _Component(match.start(), match.end(), match.start(), match.end(), "city")
            )
        return cities

    @staticmethod
    def _city_normal(word: str) -> str:
        if word in CITIES:
            return word
        try:
            return str(parse_word(word)[0].normal_form)
        except Exception:
            return word


def recognizers() -> list[Recognizer]:
    return [AddressRecognizer()]
