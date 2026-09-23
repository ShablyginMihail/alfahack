from __future__ import annotations

import re

from pii_guard.core.context import find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document, normalize
from pii_guard.core.service_words import SERVICE_WORDS
from pii_guard.ml.model import NerModel
from pii_guard.recognizers.address import ADDRESS_CONTEXT, is_bank_branch
from pii_guard.recognizers.names import (
    NAME_CONTEXT,
    PERSONAL_CONTEXT,
    parse_word,
    public_figure_context,
)

_WORD_RE = re.compile(r"[а-яёa-z]+(?:-[а-яёa-z]+)*", re.IGNORECASE)
_ADDR_TOKEN_RE = re.compile(r"[а-яёa-z0-9]+(?:-[а-яёa-z0-9]+)*", re.IGNORECASE)
_NUMBER_CONT_RE = re.compile(r"(?:[-/]\d+[а-яёa-z]?|к\d+)")
_DIGIT_CONT_RE = re.compile(r"\d+[а-яёa-z]?")

_REMOVABLE_POS = frozenset(
    {
        "VERB",
        "INFN",
        "NPRO",
        "PREP",
        "CONJ",
        "PRCL",
        "ADVB",
        "GRND",
        "PRTF",
        "PRTS",
        "INTJ",
        "PRED",
    }
)


def _is_removable(word: str) -> bool:
    parses = [p for p in parse_word(word.lower()) if p.score >= 0.05]
    if not parses:
        return False
    if any(tag in p.tag for p in parses for tag in ("Name", "Surn", "Patr")):
        return False
    if word[0].islower():
        return True
    return any(p.tag.POS in _REMOVABLE_POS for p in parses)


def _is_name_like(word: str) -> bool:
    if word.isascii():
        return True
    parses = parse_word(word.lower())
    if any(tag in p.tag for p in parses if p.score >= 0.05 for tag in ("Name", "Surn", "Patr")):
        return True
    return not parses[0].is_known


def _has_name_tag(word: str) -> bool:
    return any(
        tag in p.tag
        for p in parse_word(word.lower())
        if p.score >= 0.05
        for tag in ("Name", "Surn", "Patr")
    )


class NerRecognizer:
    name = "ner"
    pii_types = frozenset({"PERSON", "ADDRESS"})

    def __init__(self, model: NerModel) -> None:
        self._model = model

    def find(self, doc: Document) -> list[Span]:
        spans: list[Span] = []
        for entity in self._model.predict(doc.text):
            if entity.label == "PERSON":
                spans.extend(self._person_spans(doc, entity.start, entity.end, entity.score))
            elif entity.label == "ADDRESS":
                spans.extend(self._address_spans(doc, entity.start, entity.end, entity.score))
        return spans

    def _person_spans(self, doc: Document, start: int, end: int, confidence: float) -> list[Span]:
        start, end = self._expand_words(doc.text, start, end)
        words = self._span_words(doc.text, start, end)
        if not words:
            return []
        while words and _is_removable(words[0][2]):
            words.pop(0)
        while words and _is_removable(words[-1][2]):
            words.pop()
        if not words:
            return []
        if not any(_is_name_like(word) for _, _, word in words):
            return []
        span_start = words[0][0]
        span_end = words[-1][1]
        if public_figure_context(doc, span_end):
            return []
        score = 0.25 + 0.25 * confidence
        if any(_has_name_tag(word) for _, _, word in words):
            score += 0.15
        if (
            find_keyword(doc, span_start, span_end, PERSONAL_CONTEXT, 40, "before") is not None
            or find_keyword(doc, span_start, span_end, NAME_CONTEXT, 40, "before") is not None
        ):
            score += 0.2
        score = max(0.0, min(1.0, score))
        if score <= 0:
            return []
        return [Span(span_start, span_end, "PERSON", score, self.name)]

    def _address_spans(self, doc: Document, start: int, end: int, confidence: float) -> list[Span]:
        if is_bank_branch(doc, start):
            return []
        end = self._extend_number(doc.text, end)
        has_digit = any(ch.isdigit() for ch in doc.text[start:end])
        context_bonus = (
            0.2 if find_keyword(doc, start, end, ADDRESS_CONTEXT, 40, "before") is not None else 0.0
        )
        spans: list[Span] = []
        for part_start, part_end in self._split_address(doc.text, start, end):
            score = 0.25 + 0.25 * confidence
            if has_digit:
                score += 0.2
            score += context_bonus
            score = max(0.0, min(1.0, score))
            if score <= 0:
                continue
            spans.append(Span(part_start, part_end, "ADDRESS", score, self.name, part="component"))
        return spans

    @staticmethod
    def _expand_words(text: str, start: int, end: int) -> tuple[int, int]:
        while start > 0 and not text[start - 1].isspace():
            start -= 1
        while end < len(text) and not text[end].isspace():
            end += 1
        return start, end

    @staticmethod
    def _span_words(text: str, start: int, end: int) -> list[tuple[int, int, str]]:
        return [(m.start(), m.end(), m.group(0)) for m in _WORD_RE.finditer(text, start, end)]

    @staticmethod
    def _split_address(text: str, start: int, end: int) -> list[tuple[int, int]]:
        parts: list[tuple[int, int]] = []
        for m in _ADDR_TOKEN_RE.finditer(text, start, end):
            if normalize(m.group(0)) in SERVICE_WORDS:
                continue
            parts.append((m.start(), m.end()))
        return parts

    @staticmethod
    def _extend_number(text: str, end: int) -> int:
        if end > 0 and text[end - 1] in "-/":
            m = _DIGIT_CONT_RE.match(text, end)
            if m is not None:
                return m.end()
        m = _NUMBER_CONT_RE.match(text, end)
        if m is None:
            return end
        return m.end()
