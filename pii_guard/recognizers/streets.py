from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.core.service_words import SERVICE_WORDS
from pii_guard.recognizers.address import ADDRESS_CONTEXT, CITIES, is_bank_branch
from pii_guard.recognizers.names import parse_word

_HOUSE = r"\d{1,3}(?:[а-яё]|[/-]\d+[а-яё]?|[а-яё]\d+)?"
_CANDIDATE_RE = re.compile(rf"(?<!\w)([а-яё]+(?:-[а-яё]+)*)\s*[, ]\s*({_HOUSE})(?![\w/-])")

_TAIL_RE = re.compile(
    r"(?<!\w)(?:"
    r"(кв|квартира|корп|корпус|к|стр|подъезд|под|этаж|офис)\s*(\d+[а-яё]?)"
    r"|(\d+[а-яё]?)\s*(подъезд|под|этаж)"
    r")(?!\w)"
)

_UNIT_WORDS = frozenset(
    {
        "лет",
        "год",
        "года",
        "руб",
        "рублей",
        "км",
        "м",
        "мин",
        "минут",
        "шт",
        "раз",
        "раза",
        "человек",
        "градус",
    }
)
_MONTHS = frozenset(
    {
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    }
)

_STREET_CONTEXT_EXTRA = compile_keywords(["на", "по", "жду", "приеду", "привез", "адресок"])

_TAIL_WINDOW = 40


def _load_streets() -> frozenset[str]:
    path = Path(__file__).resolve().parent.parent.parent / "data" / "dicts" / "streets.txt"
    if not path.exists():
        return frozenset()
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _normalize_words(text: str) -> str:
    words: list[str] = []
    for word in text.split():
        try:
            words.append(str(parse_word(word)[0].normal_form).replace("ё", "е"))
        except Exception:
            words.append(word)
    return " ".join(words)


_STREETS = _load_streets()
_STREET_NORMAL = frozenset(_normalize_words(name) for name in _STREETS)


class StreetNameRecognizer(Recognizer):
    name = "street_name"
    pii_types = frozenset({"ADDRESS"})

    def find(self, doc: Document) -> Iterable[Span]:
        spans: list[Span] = []
        for match in _CANDIDATE_RE.finditer(doc.norm):
            word = match.group(1)
            word_start = match.start(1)
            word_end = match.end(1)
            house_start = match.start(2)
            house_end = match.end(2)
            if self._reject_after_house(doc, house_end):
                continue
            street_start, street_end, street_words = self._street_span(
                doc, word_start, word_end, word
            )
            if is_bank_branch(doc, street_start):
                continue
            city = self._city_before(doc, street_start)
            score = self._score(doc, street_words, street_start, city)
            if score is None:
                continue
            spans.append(Span(street_start, street_end, "ADDRESS", score, self.name, part="street"))
            spans.append(Span(house_start, house_end, "ADDRESS", score, self.name, part="house"))
            if city is not None:
                spans.append(Span(city[0], city[1], "ADDRESS", score, self.name, part="city"))
            spans.extend(self._tail_spans(doc, house_end, score))
        return spans

    @staticmethod
    def _street_span(
        doc: Document, word_start: int, word_end: int, word: str
    ) -> tuple[int, int, str]:
        before = doc.norm[max(0, word_start - 30) : word_start]
        match = re.search(r"([а-яё]+(?:-[а-яё]+)*)\s+$", before)
        if match is not None:
            prev = match.group(1)
            two = f"{prev} {word}"
            if _normalize_words(two) in _STREET_NORMAL:
                prev_start = word_start - (len(before) - match.start(1))
                return prev_start, word_end, two
        return word_start, word_end, word

    def _score(
        self,
        doc: Document,
        street_words: str,
        street_start: int,
        city: tuple[int, int] | None,
    ) -> float | None:
        if _normalize_words(street_words) in _STREET_NORMAL:
            score = 0.6
            if self._has_address_context(doc, street_start) or city is not None:
                score += 0.15
            return score
        if city is None or not doc.text[street_start].isupper():
            return None
        if len(street_words) < 3 or street_words in SERVICE_WORDS:
            return None
        return 0.75

    @staticmethod
    def _reject_after_house(doc: Document, house_end: int) -> bool:
        norm = doc.norm
        pos = house_end
        while pos < len(norm) and norm[pos].isspace():
            pos += 1
        if pos >= len(norm):
            return False
        if norm[pos] == "%":
            return True
        if pos + 1 < len(norm) and norm[pos] in ".," and norm[pos + 1].isdigit():
            return True
        match = re.match(r"[а-яё]+(?:-[а-яё]+)*", norm[pos:])
        if match is None:
            return False
        return match.group(0) in _UNIT_WORDS or match.group(0) in _MONTHS

    @staticmethod
    def _has_address_context(doc: Document, street_start: int) -> bool:
        if find_keyword(doc, street_start, street_start, ADDRESS_CONTEXT, 30, "before") is not None:
            return True
        return (
            find_keyword(doc, street_start, street_start, _STREET_CONTEXT_EXTRA, 30, "before")
            is not None
        )

    @staticmethod
    def _city_before(doc: Document, street_start: int) -> tuple[int, int] | None:
        before = doc.norm[max(0, street_start - 40) : street_start]
        match = re.search(r"([а-яё]+(?:-[а-яё]+)*)\s*,\s*$", before)
        if match is None:
            return None
        word = match.group(1)
        if StreetNameRecognizer._city_normal(word) not in CITIES:
            return None
        start = street_start - (len(before) - match.start(1))
        return start, start + len(word)

    @staticmethod
    def _city_normal(word: str) -> str:
        if word in CITIES:
            return word
        try:
            return str(parse_word(word)[0].normal_form)
        except Exception:
            return word

    @staticmethod
    def _tail_spans(doc: Document, house_end: int, score: float) -> list[Span]:
        spans: list[Span] = []
        pos = house_end
        limit = min(len(doc.norm), house_end + _TAIL_WINDOW)
        while pos < limit:
            while pos < limit and doc.norm[pos] in " ,":
                pos += 1
            if pos >= limit:
                break
            match = _TAIL_RE.match(doc.norm, pos, limit)
            if match is None:
                break
            number = match.group(2) or match.group(3)
            if number is None:
                break
            num_start = match.start(2) if match.group(2) else match.start(3)
            num_end = match.end(2) if match.group(2) else match.end(3)
            spans.append(
                Span(
                    num_start,
                    num_end,
                    "ADDRESS",
                    score,
                    StreetNameRecognizer.name,
                    part="apartment",
                )
            )
            pos = match.end()
        return spans


def recognizers() -> list[Recognizer]:
    return [StreetNameRecognizer()]
