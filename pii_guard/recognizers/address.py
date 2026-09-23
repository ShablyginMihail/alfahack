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

CITY_ABBR_MARKERS = r"(?:г\.|гор\.|пос\.|с\.|дер\.|пгт|ст-ца|клх|ст\.|п\.|рп|р\.п\.|аул|х\.)"
CITY_WORD_MARKERS = (
    r"(?:город|города|городе|поселок|поселке|село|селе|деревня|деревне|станица|хутор)"
)
CITY_RE = re.compile(
    rf"(?<!\w)(?:{CITY_ABBR_MARKERS}\s*[:.]?\s*|{CITY_WORD_MARKERS}\s*:?\s*)"
    rf"([а-яё]{{2,}}(?:-[а-яё]+)*(?:\s+[а-яё]+(?:-[а-яё]+)*)?)(?!\w)"
)

STREET_ABBR_MARKERS = (
    r"(?:ул\.|пр\.|пер\.|ш\.|наб\.|пл\.|туп\.|бул\.|бульв\.|алл\.|просп\.|"
    r"пр-т(?!\w)|пр-кт(?!\w)|пр-д(?!\w)|б-р(?!\w)|кв-л(?!\w)|мкр(?!\w))"
)
STREET_WORD_MARKERS = (
    r"(?:улица(?!\w)|улицы(?!\w)|улице(?!\w)|улицу(?!\w)|улицей(?!\w)|"
    r"проспект(?!\w)|проспекта(?!\w)|проспекте(?!\w)|"
    r"переулок(?!\w)|переулка(?!\w)|переулке(?!\w)|"
    r"шоссе(?!\w)|бульвар(?!\w)|бульваре(?!\w)|"
    r"набережная(?!\w)|набережной(?!\w)|"
    r"площадь(?!\w)|площади(?!\w)|проезд(?!\w)|проезде(?!\w)|"
    r"тупик(?!\w)|аллея(?!\w)|линия(?!\w)|микрорайон(?!\w))"
)
_STREET_WORD = r"[а-яё0-9]+(?:-[а-яё0-9]+)*"
STREET_RE = re.compile(
    rf"(?<!\w)(?:{STREET_ABBR_MARKERS}\s*[:.]?\s*|{STREET_WORD_MARKERS}\s*:?\s*)"
    rf"({_STREET_WORD}(?:\s+{_STREET_WORD}){{0,2}})(?!\w)"
)
STREET_AFTER_MARKERS = (
    r"(?:проспект|проспекте|проспекта|пр-т|улица|улице|улицы|улицу|шоссе|бульвар|бульваре|б-р|"
    r"переулок|переулке|переулка|проезд|проезде|набережная|набережной|тупик|аллея|аллее|"
    r"площадь|площади|ул\.|пер\.|пр\.|ш\.|наб\.|бул\.)"
)
STREET_AFTER_RE = re.compile(
    rf"(?<!\w)({_STREET_WORD}(?:\s+{_STREET_WORD})?)\s*{STREET_AFTER_MARKERS}(?!\w)"
)

REGION_RE = re.compile(r"(?<!\w)([а-яё]+(?:-[а-яё]+)*)\s+(?:обл\.|область|край)(?!\w)")
REGION_REPUBLIC_RE = re.compile(r"(?<!\w)республик\w*\s+([а-яё]+(?:-[а-яё]+)*)(?!\w)")
REGION_AO_RE = re.compile(r"(?<!\w)([а-яё]+(?:-[а-яё]+)*)\s+(?:АО|автономный\s+округ)(?!\w)")

HOUSE_RE = re.compile(
    r"(?<!\w)(?:д\.|дом|дома|доме|д)\s*[:.]?\s*(\d+(?:[/-]\d+)?(?:[а-яё]\d*)?)(?!\w)"
)
CORPS_RE = re.compile(
    r"(?<!\w)(?:корпус|корпуса|корп|строение|строения|стр|корп\.|к\.|стр\.|лит\.)"
    r"\s*[:.]?\s*(\d+[а-яё]?(?:[/-]\d+)?)(?!\w)"
)
APARTMENT_RE = re.compile(
    r"(?<!\w)(?:кв\.|кв|квартира|квартиры|квартире|оф\.|офис|пом\.|помещение)\s*[:.]?\s*(\d+[а-яё]?)(?!\w)"
)

_HOUSE_NUMBER_RE = re.compile(r"\d+(?:[/-]\d+)?(?:[а-яё]\d*)?")

ENTRANCE_RE = re.compile(r"(?<!\w)(?:подъезд|подьезд|под\.|под)\s*[:.]?\s*(\d+)(?!\w)")
ENTRANCE_AFTER_RE = re.compile(r"(?<!\w)(\d+)(?:-?й)?\s*(?:подъезд|подьезд|под)(?!\w)")
FLOOR_RE = re.compile(r"(?<!\w)(?:этаж|эт\.|эт)\s*[:.]?\s*(\d+)(?!\w)")
FLOOR_AFTER_RE = re.compile(r"(?<!\w)(\d+)(?:-?й)?\s*(?:этаж|эт)(?!\w)")

WORD_RE = re.compile(r"[а-яё]+(?:-[а-яё]+)*")

# подъезд и этаж — адрес только в цепочке с другими частями адреса
_TAIL_ONLY_PARTS = frozenset({"entrance", "floor"})

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
        "переехал",
        "переехала",
        "прописка",
        "регистрац",
        "по адресу",
        "доставьте",
        "курьер",
        "отправьте",
        "живет",
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
        "адрес офиса",
        "в офисе",
        "офис расположен",
        "офис находится",
        "офис компании",
        "офиса компании",
        "юридический адрес",
    ]
)
BANK_OFFICE_RE = re.compile(
    r"(?<!\w)офис\w*(?:\s+[а-яё-]+){0,2}\s+"
    r"(?:[а-яё-]*банк[а-яё-]*|втб|тинькофф|райффайзен)(?!\w)"
)
BANK_EXCEPTION = compile_keywords(
    [
        "прожива",
        "прописан",
        "зарегистрирован",
        "адрес регистрации",
        "адрес проживания",
        "мой адрес",
        "клиент",
        "жительств",
        "живет",
        "живу",
        "доставк",
        "регистрац",
        "прописк",
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


def is_bank_branch(doc: Document, start: int) -> bool:
    before = doc.norm[max(0, start - 60) : start]
    has_bank_context = (
        find_keyword(doc, start, start, BANK_CONTEXT, 60, "before") is not None
        or BANK_OFFICE_RE.search(before) is not None
    )
    if not has_bank_context:
        return False
    return find_keyword(doc, start, start, BANK_EXCEPTION, 60, "before") is None


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
        components.extend(self._cities_before_components(doc, components))
        components.extend(self._houses_after_street(doc, components))
        components.extend(self._street_after_city(doc, components))
        components = self._dedupe(components)
        spans: list[Span] = []
        for chain in self._group_chains(doc, components):
            if self._is_bank_branch(doc, chain[0].full_start):
                continue
            if len(chain) >= 2:
                for comp in chain:
                    spans.append(
                        Span(comp.start, comp.end, "ADDRESS", 0.85, self.name, part=comp.part)
                    )
            elif chain[0].part not in _TAIL_ONLY_PARTS:
                comp = chain[0]
                score = self._single_score(doc, comp)
                spans.append(
                    Span(comp.start, comp.end, "ADDRESS", score, self.name, part=comp.part)
                )
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
        components.extend(self._find_cities_without_marker(doc))
        components.extend(self._entrances(doc))
        components.extend(self._floors(doc))
        components.extend(self._street_before_tail(doc, components))
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
        components: list[_Component] = []
        for m in STREET_RE.finditer(doc.norm):
            components.extend(AddressRecognizer._split_street(m))
        for m in STREET_AFTER_RE.finditer(doc.norm):
            name = m.group(1)
            words = [w for w in name.split() if w]
            if not words or len(words) > 2:
                continue
            if len(words) == 2 and words[0] in FUNCTION_WORDS:
                second = words[1]
                if AddressRecognizer._valid_street_after(second):
                    start = m.start(1) + name.index(second)
                    components.append(_Component(start, m.end(1), m.start(), m.end(), "street"))
                continue
            if AddressRecognizer._valid_street_after(name):
                components.append(_Component(m.start(1), m.end(1), m.start(), m.end(), "street"))
        return components

    @staticmethod
    def _split_street(m: re.Match[str]) -> list[_Component]:
        name = m.group(1)
        words = name.split()
        house_idx = -1
        for i in range(len(words) - 1, -1, -1):
            if _HOUSE_NUMBER_RE.fullmatch(words[i]):
                house_idx = i
                break
        if house_idx <= 0:
            return [_Component(m.start(1), m.end(1), m.start(), m.end(), "street")]
        positions: list[tuple[int, int]] = []
        pos = 0
        for w in words:
            idx = name.index(w, pos)
            positions.append((idx, idx + len(w)))
            pos = idx + len(w)
        street_start = m.start(1) + positions[0][0]
        street_end = m.start(1) + positions[house_idx - 1][1]
        house_start = m.start(1) + positions[house_idx][0]
        house_end = m.start(1) + positions[house_idx][1]
        return [
            _Component(street_start, street_end, m.start(), street_end, "street"),
            _Component(house_start, house_end, house_start, house_end, "house"),
        ]

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
    def _entrances(doc: Document) -> list[_Component]:
        components = [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "entrance")
            for m in ENTRANCE_RE.finditer(doc.norm)
        ]
        components.extend(
            _Component(m.start(1), m.end(1), m.start(), m.end(), "entrance")
            for m in ENTRANCE_AFTER_RE.finditer(doc.norm)
        )
        return components

    @staticmethod
    def _floors(doc: Document) -> list[_Component]:
        components = [
            _Component(m.start(1), m.end(1), m.start(), m.end(), "floor")
            for m in FLOOR_RE.finditer(doc.norm)
        ]
        components.extend(
            _Component(m.start(1), m.end(1), m.start(), m.end(), "floor")
            for m in FLOOR_AFTER_RE.finditer(doc.norm)
        )
        return components

    def _street_before_tail(self, doc: Document, components: list[_Component]) -> list[_Component]:
        result: list[_Component] = []
        for comp in list(components):
            if comp.part not in {"apartment", "house", "entrance"}:
                continue
            before = doc.norm[max(0, comp.full_start - 40) : comp.full_start]
            match = re.search(
                r"([а-яё]+(?:-[а-яё]+)*)\s+(\d+(?:[/-]\d+)?[а-яё]?)(?:\s*,\s*|\s+)$",
                before,
            )
            if match is None:
                continue
            word = match.group(1)
            if word in FUNCTION_WORDS or word in STREET_STOP_WORDS:
                continue
            if not self._is_adjective(word):
                continue
            street_start = comp.full_start - (len(before) - match.start(1))
            street_end = comp.full_start - (len(before) - match.end(1))
            house_start = comp.full_start - (len(before) - match.start(2))
            house_end = comp.full_start - (len(before) - match.end(2))
            result.append(_Component(street_start, street_end, street_start, street_end, "street"))
            result.append(_Component(house_start, house_end, house_start, house_end, "house"))
        return result

    @staticmethod
    def _countries(doc: Document) -> list[_Component]:
        return [
            _Component(m.start(), m.end(), m.start(), m.end(), "country")
            for m in COUNTRY_RE.finditer(doc.norm)
        ]

    def _cities_before_components(
        self, doc: Document, components: list[_Component]
    ) -> list[_Component]:
        result: list[_Component] = []
        for comp in components:
            before = doc.norm[max(0, comp.full_start - 40) : comp.full_start]
            match = re.search(r"([а-яё]+(?:-[а-яё]+)*)\s*,\s*$", before)
            if match is None:
                continue
            word = match.group(1)
            if self._city_normal(word) not in CITIES:
                continue
            start = comp.full_start - (len(before) - match.start(1))
            end = start + len(word)
            result.append(_Component(start, end, start, end, "city"))
        return result

    def _houses_after_street(self, doc: Document, components: list[_Component]) -> list[_Component]:
        result: list[_Component] = []
        for comp in components:
            if comp.part != "street":
                continue
            after = doc.norm[comp.full_end : comp.full_end + 15]
            match = re.match(r"^(?:\s*,\s*|\s+)(\d+(?:[/-]\d+)?[а-яё]?)(?![\w/-])", after)
            if match is None:
                continue
            start = comp.full_end + match.start(1)
            end = comp.full_end + match.end(1)
            result.append(_Component(start, end, comp.full_end, end, "house"))
        return result

    def _street_after_city(self, doc: Document, components: list[_Component]) -> list[_Component]:
        result: list[_Component] = []
        for comp in components:
            if comp.part != "city":
                continue
            after = doc.norm[comp.full_end : comp.full_end + 60]
            match = re.match(
                r"^\s*,\s*([а-яё]+(?:-[а-яё]+)*)\s+(\d+(?:[/-]\d+)?[а-яё]?)(?![\w/-])", after
            )
            if match is None:
                continue
            name = match.group(1)
            if name in FUNCTION_WORDS or name in STREET_STOP_WORDS:
                continue
            if not self._is_adjective(name):
                continue
            street_start = comp.full_end + match.start(1)
            street_end = comp.full_end + match.end(1)
            house_start = comp.full_end + match.start(2)
            house_end = comp.full_end + match.end(2)
            result.append(_Component(street_start, street_end, street_start, street_end, "street"))
            result.append(_Component(house_start, house_end, house_start, house_end, "house"))
        return result

    @staticmethod
    def _dedupe(components: list[_Component]) -> list[_Component]:
        seen: set[tuple[int, int]] = set()
        result: list[_Component] = []
        for comp in components:
            key = (comp.start, comp.end)
            if key in seen:
                continue
            seen.add(key)
            result.append(comp)
        return result

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
        return is_bank_branch(doc, start)

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
