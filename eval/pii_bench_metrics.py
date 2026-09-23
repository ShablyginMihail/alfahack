from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass

from pii_guard.core.service_words import SERVICE_WORDS


@dataclass(frozen=True, slots=True)
class Entity:
    start: int
    end: int
    type: str
    text: str


def parse_entities(value) -> list[Entity]:
    if value is None:
        return []
    if isinstance(value, str):
        value = json.loads(value)
    result: list[Entity] = []
    for item in value:
        result.append(
            Entity(
                start=int(item["start"]),
                end=int(item["end"]),
                type=str(item["type"]),
                text=str(item["text"]),
            )
        )
    return result


def _word_at(text: str, pos: int) -> str | None:
    if pos < 0 or pos >= len(text) or not text[pos].isalnum():
        return None
    start = pos
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "-"):
        start -= 1
    end = pos + 1
    while end < len(text) and (text[end].isalnum() or text[end] == "-"):
        end += 1
    return text[start:end].lower()


def entity_status(
    text: str,
    start: int,
    end: int,
    masked: set[int],
    service_words: frozenset[str] = SERVICE_WORDS,
) -> str:
    significant = 0
    covered = 0
    for i in range(start, end):
        if not text[i].isalnum():
            continue
        word = _word_at(text, i)
        if word is not None and word in service_words:
            continue
        significant += 1
        if i in masked:
            covered += 1
    if significant == 0 or covered == significant:
        return "closed"
    if covered == 0:
        return "missed"
    return "partial"


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def aggregate_entity_docs(docs) -> tuple[dict, int, int]:
    per_type: dict[str, dict[str, int]] = {}
    leak_docs = 0
    total_docs = 0
    for entities, statuses in docs:
        total_docs += 1
        leaked = False
        for entity, status in zip(entities, statuses, strict=True):
            stats = per_type.setdefault(entity.type, {"closed": 0, "partial": 0, "missed": 0})
            stats[status] += 1
            if status != "closed":
                leaked = True
        if leaked:
            leak_docs += 1
    return per_type, leak_docs, total_docs


def aggregate_domain_docs(docs) -> tuple[int, int]:
    fp = sum(1 for has_mask in docs if has_mask)
    return fp, len(docs)


def time_stats(times: list[float]) -> tuple[float, float]:
    if not times:
        return (0.0, 0.0)
    mean = statistics.mean(times)
    ordered = sorted(times)
    idx = min(len(ordered) - 1, int(len(ordered) * 95 / 100))
    return (mean, ordered[idx])
