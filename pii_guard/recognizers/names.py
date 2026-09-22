from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import pymorphy3

from pii_guard.core.context import compile_keywords, find_keyword
from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer

TOKEN_RE = re.compile(r"[а-яё]\.|[а-яё]+(?:-[а-яё]+)*")

PATR_END_RE = re.compile(r"(?:ович|евич|овна|евна|ична|инична)(?:а|у|е|ой|ом|ы|и|ю|ей|ою)?$")
SURN_END_RE = re.compile(
    r"(?:ов|ев|ин|ын|ский|цкий|ова|ева|ина|ская|цкая)"
    r"(?:а|у|е|ой|ом|ы|и|ю|ей|ого|ому|ым|ем|их)?$"
)

PERSONAL_CONTEXT = compile_keywords(
    [
        "клиент",
        "гражданин",
        "гражданк",
        "господин",
        "госпож",
        "г-н",
        "г-жа",
        "уважаем",
        "фио",
        "заемщик",
        "получател",
        "отправител",
        "плательщик",
        "владел",
        "меня зовут",
        "зовут",
        "сотрудник",
    ]
)
CULTURAL_CONTEXT = compile_keywords(
    [
        "поэт",
        "писател",
        "композитор",
        "художник",
        "учен",
        "памятник",
        "музей",
        "театр",
        "улиц",
        "проспект",
        "площад",
        "метро",
        "имени",
        "стих",
        "роман",
        "произведени",
        "автор",
        "царь",
        "император",
    ]
)

FUNCTION_WORDS = frozenset(
    {
        "и",
        "в",
        "во",
        "на",
        "с",
        "со",
        "по",
        "к",
        "ко",
        "от",
        "о",
        "об",
        "у",
        "за",
        "из",
        "до",
        "при",
        "про",
        "без",
        "для",
        "над",
        "под",
        "через",
        "между",
        "перед",
        "после",
        "около",
        "возле",
        "а",
        "но",
        "или",
        "что",
        "как",
        "же",
        "бы",
        "не",
        "ни",
        "то",
        "это",
        "он",
        "она",
        "оно",
        "они",
        "мы",
        "вы",
        "ты",
        "я",
        "его",
        "ее",
        "её",
        "их",
        "мой",
        "твой",
        "наш",
        "ваш",
        "свой",
        "этот",
        "тот",
        "такой",
        "весь",
        "сам",
        "себя",
        "который",
        "чтобы",
        "если",
        "хотя",
        "потому",
        "поэтому",
        "также",
        "тоже",
        "даже",
        "уже",
        "еще",
        "ещё",
        "только",
        "вот",
        "там",
        "тут",
        "здесь",
        "сейчас",
        "потом",
        "всегда",
        "никогда",
        "очень",
        "совсем",
        "почти",
        "опять",
        "снова",
        "вдруг",
        "наконец",
        "например",
        "именно",
        "тогда",
        "теперь",
        "все",
        "всё",
        "всех",
        "всем",
        "всеми",
        "всего",
        "всему",
        "всей",
        "всю",
        "всею",
    }
)

PATTERNS: tuple[tuple[tuple[str, ...], float], ...] = (
    (("SURN", "NAME", "PATR"), 0.95),
    (("NAME", "PATR", "SURN"), 0.95),
    (("SURN", "INIT", "INIT"), 0.9),
    (("INIT", "INIT", "SURN"), 0.9),
    (("NAME", "PATR"), 0.85),
    (("SURN", "INIT"), 0.9),
    (("INIT", "SURN"), 0.9),
    (("SURN", "NAME"), 0.8),
    (("NAME", "SURN"), 0.8),
)


@lru_cache(maxsize=1)
def get_morph() -> pymorphy3.MorphAnalyzer:
    return pymorphy3.MorphAnalyzer()


@lru_cache(maxsize=100_000)
def _parse(word: str) -> tuple[Any, ...]:
    return tuple(get_morph().parse(word))


def _load_public_figures() -> frozenset[str]:
    path = Path(__file__).resolve().parent.parent.parent / "data" / "dicts" / "public_figures.txt"
    if not path.exists():
        return frozenset()
    return frozenset(
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


PUBLIC_FIGURES = _load_public_figures()


@dataclass(slots=True)
class _Token:
    start: int
    end: int
    text: str
    is_init: bool
    roles: frozenset[str] = field(default_factory=frozenset)
    normal: str = ""


class NameRecognizer(Recognizer):
    name = "name"
    pii_types = frozenset({"PERSON"})

    def find(self, doc: Document) -> Iterable[Span]:
        tokens = self._tokenize(doc)
        if not tokens:
            return []
        for token in tokens:
            self._classify(token)
        self._apply_fallbacks(doc, tokens)

        spans: list[Span] = []
        i = 0
        while i < len(tokens):
            matched = self._match_combination(doc, tokens, i)
            if matched is not None:
                span, end = matched
                if not self._is_public_figure(doc, span, tokens, i, end):
                    spans.append(span)
                i = end
                continue
            token = tokens[i]
            if token.roles & {"SURN", "NAME"} and not (token.roles & {"PATR"}):
                role = "SURN" if "SURN" in token.roles else "NAME"
                if (
                    find_keyword(doc, token.start, token.end, PERSONAL_CONTEXT, 30, "before")
                    is not None
                ):
                    score = 0.7 if role == "SURN" else 0.6
                    span = Span(token.start, token.end, "PERSON", score, self.name)
                    if not self._is_public_figure_single(doc, span, token):
                        spans.append(span)
            i += 1
        return spans

    def _tokenize(self, doc: Document) -> list[_Token]:
        tokens: list[_Token] = []
        for match in TOKEN_RE.finditer(doc.norm):
            text = match.group(0)
            is_init = text.endswith(".")
            if not is_init and text in FUNCTION_WORDS:
                continue
            tokens.append(_Token(match.start(), match.end(), text, is_init))
        return tokens

    def _classify(self, token: _Token) -> None:
        if token.is_init:
            token.roles = frozenset({"INIT"})
            return
        roles: set[str] = set()
        normal = token.text
        for parse in _parse(token.text):
            if parse.score < 0.05:
                continue
            if "Name" in parse.tag:
                roles.add("NAME")
            if "Surn" in parse.tag:
                roles.add("SURN")
            if "Patr" in parse.tag:
                roles.add("PATR")
            if parse.normal_form:
                normal = parse.normal_form
        token.roles = frozenset(roles)
        token.normal = normal

    def _apply_fallbacks(self, doc: Document, tokens: list[_Token]) -> None:
        for i, token in enumerate(tokens):
            if token.is_init:
                continue
            roles = set(token.roles)
            if PATR_END_RE.search(token.text) and "PATR" not in roles:
                roles.add("PATR")
            if (
                SURN_END_RE.search(token.text)
                and "SURN" not in roles
                and self._has_name_neighbor(doc, tokens, i)
            ):
                roles.add("SURN")
            token.roles = frozenset(roles)

    def _has_name_neighbor(self, doc: Document, tokens: list[_Token], i: int) -> bool:
        for j in (i - 1, i + 1):
            if (
                0 <= j < len(tokens)
                and tokens[j].roles & {"NAME", "INIT"}
                and self._adjacent(doc, tokens[i], tokens[j])
            ):
                return True
        return False

    @staticmethod
    def _adjacent(doc: Document, t1: _Token, t2: _Token) -> bool:
        return all(ch.isspace() for ch in doc.norm[t1.end : t2.start])

    def _match_combination(
        self, doc: Document, tokens: list[_Token], i: int
    ) -> tuple[Span, int] | None:
        for pattern, score in PATTERNS:
            if i + len(pattern) > len(tokens):
                continue
            ok = True
            for j, role in enumerate(pattern):
                if role not in tokens[i + j].roles:
                    ok = False
                    break
                if j > 0 and not self._adjacent(doc, tokens[i + j - 1], tokens[i + j]):
                    ok = False
                    break
            if ok:
                start = tokens[i].start
                end = tokens[i + len(pattern) - 1].end
                return Span(start, end, "PERSON", score, self.name), i + len(pattern)
        return None

    def _is_public_figure(
        self, doc: Document, span: Span, tokens: list[_Token], start: int, end: int
    ) -> bool:
        if find_keyword(doc, span.start, span.end, PERSONAL_CONTEXT, 40, "both") is not None:
            return False
        surname = self._surname_normal(tokens, start, end)
        if surname and surname in PUBLIC_FIGURES:
            return True
        return find_keyword(doc, span.start, span.end, CULTURAL_CONTEXT, 40, "before") is not None

    def _is_public_figure_single(self, doc: Document, span: Span, token: _Token) -> bool:
        if find_keyword(doc, span.start, span.end, PERSONAL_CONTEXT, 40, "both") is not None:
            return False
        if "SURN" in token.roles and token.normal in PUBLIC_FIGURES:
            return True
        return find_keyword(doc, span.start, span.end, CULTURAL_CONTEXT, 40, "before") is not None

    @staticmethod
    def _surname_normal(tokens: list[_Token], start: int, end: int) -> str:
        for token in tokens[start:end]:
            if "SURN" in token.roles:
                return token.normal
        return ""


def recognizers() -> list[Recognizer]:
    return [NameRecognizer()]
