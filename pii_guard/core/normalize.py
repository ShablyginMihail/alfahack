from __future__ import annotations

import re
from dataclasses import dataclass

_DASHES = "‐‑‒–—―−⁃﹣－"
_SPACES = (
    "\u00a0\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
)
_ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
_QUOTES = "«»„“”‟″"
_APOSTROPHES = "‘’‚‛′"

_TRANSLATE_TABLE = str.maketrans(
    {
        **{ch: "-" for ch in _DASHES},
        **{ch: " " for ch in _SPACES},
        **{ch: " " for ch in _ZERO_WIDTH},
        **{ch: '"' for ch in _QUOTES},
        **{ch: "'" for ch in _APOSTROPHES},
        "ё": "е",
        "Ё": "е",
    }
)

_LOOKALIKES = str.maketrans(
    {
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "н",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "x": "х",
        "y": "у",
    }
)
_LOOKALIKE_LATIN = frozenset("abcehkmoptxy")
_LOOKALIKE_LATIN_RE = re.compile(r"[abcehkmoptxy]")
_CYRILLIC_RE = re.compile(r"[а-яё]")
_MIXED_WORD_RE = re.compile(r"(?<![a-zа-яё])(?=[a-zа-яё]*[а-яё])[a-zа-яё]*[a-z][a-zа-яё]*")


def _replace_lookalikes(text: str) -> str:
    if _LOOKALIKE_LATIN_RE.search(text) is None or _CYRILLIC_RE.search(text) is None:
        return text
    return _MIXED_WORD_RE.sub(_replace_word, text)


def _replace_word(match: re.Match[str]) -> str:
    word = match.group(0)
    latin = [ch for ch in word if "a" <= ch <= "z"]
    if not latin or any(ch not in _LOOKALIKE_LATIN for ch in latin):
        return word
    return word.translate(_LOOKALIKES)


def normalize(text: str) -> str:
    lowered = text.lower()
    if len(lowered) == len(text):
        result = lowered.translate(_TRANSLATE_TABLE)
    else:
        chars: list[str] = []
        for ch in text:
            lowered_ch = ch.lower()
            chars.append(lowered_ch if len(lowered_ch) == 1 else ch)
        result = "".join(chars).translate(_TRANSLATE_TABLE)
    return _replace_lookalikes(result)


@dataclass(frozen=True, slots=True)
class Document:
    text: str
    norm: str

    @classmethod
    def from_text(cls, text: str) -> Document:
        return cls(text=text, norm=normalize(text))
