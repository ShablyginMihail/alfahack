from __future__ import annotations

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


def normalize(text: str) -> str:
    lowered = text.lower()
    if len(lowered) == len(text):
        return lowered.translate(_TRANSLATE_TABLE)

    chars: list[str] = []
    for ch in text:
        lowered_ch = ch.lower()
        chars.append(lowered_ch if len(lowered_ch) == 1 else ch)
    return "".join(chars).translate(_TRANSLATE_TABLE)


@dataclass(frozen=True, slots=True)
class Document:
    text: str
    norm: str

    @classmethod
    def from_text(cls, text: str) -> Document:
        return cls(text=text, norm=normalize(text))
