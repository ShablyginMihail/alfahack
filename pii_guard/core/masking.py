from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pii_guard.core.models import MaskResult, Replacement, Span
from pii_guard.core.normalize import normalize
from pii_guard.core.policy import Profile
from pii_guard.core.types import TypeRegistry


@dataclass(frozen=True, slots=True)
class PartialSpec:
    keep_start: int = 0
    keep_end: int = 0


DEFAULT_PARTIAL_SPECS: dict[str, PartialSpec] = {
    "PASSPORT": PartialSpec(2, 2),
    "CARD_NUMBER": PartialSpec(4, 4),
    "PHONE": PartialSpec(1, 2),
    "INN": PartialSpec(2, 2),
    "DRIVER_LICENSE": PartialSpec(2, 2),
    "FOREIGN_PASSPORT": PartialSpec(2, 2),
    "SNILS": PartialSpec(0, 2),
    "PASSPORT:series": PartialSpec(2, 0),
    "PASSPORT:number": PartialSpec(0, 2),
    "DRIVER_LICENSE:series": PartialSpec(2, 0),
    "DRIVER_LICENSE:number": PartialSpec(0, 2),
}


def mask_partial(value: str, spec: PartialSpec, mask_char: str = "*") -> str:
    significant = [i for i, ch in enumerate(value) if ch.isalnum()]
    keep = spec.keep_start + spec.keep_end
    if len(significant) <= keep:
        keep_indices: set[int] = set()
    else:
        keep_indices = set(significant[: spec.keep_start]) | set(
            significant[len(significant) - spec.keep_end :]
        )
    chars = list(value)
    for i in significant:
        if i not in keep_indices:
            chars[i] = mask_char
    return "".join(chars)


def mask_initials(value: str) -> str:
    words: list[str] = []
    current: list[str] = []
    for ch in value:
        if ch.isalpha() or (ch == "-" and current):
            current.append(ch)
        else:
            if current:
                words.append("".join(current))
                current = []
    if current:
        words.append("".join(current))

    if not words:
        return mask_partial(value, PartialSpec(0, 0))

    return " ".join(word[0].upper() + "." for word in words)


def mask_email(value: str, mask_char: str = "*") -> str:
    at = value.find("@")
    if at < 0:
        return mask_partial(value, PartialSpec(0, 0))
    local = value[:at]
    if not local:
        return value
    return local[0] + mask_char * (len(local) - 1) + value[at:]


def mask_phone(value: str, mask_char: str = "*") -> str:
    digits_pos = [i for i, ch in enumerate(value) if ch.isdigit()]
    digits_str = "".join(value[i] for i in digits_pos)
    n = len(digits_str)

    code_len = 0
    plus = value.find("+")
    if plus >= 0:
        run = 0
        i = plus + 1
        while i < len(value) and value[i].isdigit():
            run += 1
            i += 1
        if run <= 3:
            code_len = run
        else:
            code_len = 1 if digits_str[0] in ("7", "1") else 3
    elif n == 11 and digits_str[0] in ("8", "7"):
        code_len = 1

    keep: set[int] = set(digits_pos[:code_len])
    if n - code_len >= 2:
        keep.add(digits_pos[-1])
        keep.add(digits_pos[-2])

    chars = list(value)
    for i in digits_pos:
        if i not in keep:
            chars[i] = mask_char
    return "".join(chars)


class _TokenNumbering:
    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._numbers: dict[tuple[str, str], int] = {}

    def number(self, pii_type: str, original: str) -> int:
        key = "".join(c for c in normalize(original) if c.isalnum())
        type_key = (pii_type, key)
        if type_key not in self._numbers:
            self._counters[pii_type] = self._counters.get(pii_type, 0) + 1
            self._numbers[type_key] = self._counters[pii_type]
        return self._numbers[type_key]


class DefaultMasker:
    def __init__(
        self,
        type_registry: TypeRegistry,
        partial_specs: Mapping[str, PartialSpec] | None = None,
        mask_char: str = "*",
    ) -> None:
        self._registry = type_registry
        self._partial_specs = dict(DEFAULT_PARTIAL_SPECS)
        if partial_specs:
            self._partial_specs.update(partial_specs)
        self._mask_char = mask_char

    def apply(self, text: str, spans: Sequence[Span], profile: Profile) -> MaskResult:
        style = profile.mask_style
        if style == "partial":
            masker = self._partial_mask
        elif style == "label":
            masker = self._label_mask
        elif style == "token":
            numbering = _TokenNumbering()

            def masker(span: Span, original: str) -> str:
                return self._token_mask(span, original, numbering)

        else:
            raise ValueError(f"unknown mask_style: {style!r}")

        replacements: list[Replacement] = []
        parts: list[str] = []
        cursor = 0
        masked_len = 0
        for span in spans:
            original = text[span.start : span.end]
            masked = masker(span, original)
            parts.append(text[cursor : span.start])
            masked_len += len(parts[-1])
            parts.append(masked)
            replacements.append(
                Replacement(
                    start=span.start,
                    end=span.end,
                    masked_start=masked_len,
                    original=original,
                    masked=masked,
                    pii_type=span.pii_type,
                )
            )
            masked_len += len(masked)
            cursor = span.end
        parts.append(text[cursor:])
        return MaskResult(text="".join(parts), replacements=tuple(replacements))

    def _partial_mask(self, span: Span, original: str) -> str:
        if span.pii_type in ("PERSON", "CARDHOLDER"):
            return mask_initials(original)
        if span.pii_type == "EMAIL":
            return mask_email(original, self._mask_char)
        if span.pii_type == "PHONE":
            return mask_phone(original, self._mask_char)
        key = f"{span.pii_type}:{span.part}" if span.part else span.pii_type
        spec = self._partial_specs.get(
            key, self._partial_specs.get(span.pii_type, PartialSpec(0, 0))
        )
        return mask_partial(original, spec, self._mask_char)

    def _label_mask(self, span: Span, original: str) -> str:
        return f"[{self._registry.label(span.pii_type)}]"

    def _token_mask(self, span: Span, original: str, numbering: _TokenNumbering) -> str:
        number = numbering.number(span.pii_type, original)
        return f"[{self._registry.label(span.pii_type)}_{number}]"
