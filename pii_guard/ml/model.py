from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class NerEntity:
    start: int
    end: int
    label: str
    score: float


class NerModel(Protocol):
    def predict(self, text: str) -> list[NerEntity]: ...


class NerUnavailable(Exception):
    pass


_LABEL_MAP = {"PER": "PERSON", "ADDRESS": "ADDRESS"}


class TransformersNerModel:
    def __init__(
        self,
        model_id: str,
        threads: int = 1,
        pipeline: Callable[[str], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._model_id = model_id
        self._threads = threads
        self._pipeline = pipeline
        self._loaded = False

    def load(self) -> None:
        if self._pipeline is not None:
            self._loaded = True
            return
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise NerUnavailable(
                "NER-модель недоступна: не установлены torch или transformers"
            ) from exc
        torch.set_num_threads(self._threads)
        self._pipeline = pipeline(
            "token-classification", model=self._model_id, aggregation_strategy="simple"
        )
        self._loaded = True

    def predict(self, text: str) -> list[NerEntity]:
        if not self._loaded:
            self.load()
        if self._pipeline is None:
            raise NerUnavailable("NER-модель не загружена")
        raw = self._pipeline(text)
        entities: list[NerEntity] = []
        for item in raw:
            label = _LABEL_MAP.get(item.get("entity_group") or item.get("entity") or "")
            if label is None:
                continue
            entities.append(
                NerEntity(int(item["start"]), int(item["end"]), label, float(item["score"]))
            )
        return self._merge(entities, text)

    @staticmethod
    def _merge(entities: list[NerEntity], text: str) -> list[NerEntity]:
        if not entities:
            return []
        merged: list[NerEntity] = []
        current = entities[0]
        for nxt in entities[1:]:
            if nxt.label == current.label and nxt.start - current.end <= 1:
                current = NerEntity(
                    current.start, nxt.end, current.label, min(current.score, nxt.score)
                )
            else:
                merged.append(current)
                current = nxt
        merged.append(current)
        return [TransformersNerModel._trim(entity, text) for entity in merged]

    @staticmethod
    def _trim(entity: NerEntity, text: str) -> NerEntity:
        start = max(0, entity.start)
        end = min(len(text), entity.end)
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return NerEntity(start, end, entity.label, entity.score)
