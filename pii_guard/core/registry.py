from __future__ import annotations

import importlib
from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from pii_guard.core.models import Span
from pii_guard.core.normalize import Document


@runtime_checkable
class Recognizer(Protocol):
    name: str
    pii_types: frozenset[str]

    def find(self, doc: Document) -> Iterable[Span]: ...


class RecognizerRegistry:
    def __init__(self) -> None:
        self._recognizers: list[Recognizer] = []

    def register(self, recognizer: Recognizer) -> None:
        self._recognizers.append(recognizer)

    def all(self) -> tuple[Recognizer, ...]:
        return tuple(self._recognizers)

    def for_types(self, types: frozenset[str] | None) -> tuple[Recognizer, ...]:
        if types is None:
            return self.all()
        return tuple(recognizer for recognizer in self._recognizers if recognizer.pii_types & types)

    @classmethod
    def from_modules(cls, module_names: Iterable[str]) -> RecognizerRegistry:
        registry = cls()
        for module_name in module_names:
            module = importlib.import_module(module_name)
            for recognizer in module.recognizers():
                registry.register(recognizer)
        return registry
