from __future__ import annotations


class ConcurrencyGate:
    def __init__(self, limit: int, max_weight: int = 0) -> None:
        self._limit = limit
        self._max_weight = max_weight
        self._count = 0
        self._weight = 0

    def try_enter(self, weight: int = 0) -> bool:
        if self._count >= self._limit:
            return False
        if self._count > 0 and self._weight + weight > self._max_weight:
            return False
        self._count += 1
        self._weight += weight
        return True

    def exit(self, weight: int = 0) -> None:
        if self._count > 0:
            self._count -= 1
        self._weight = max(0, self._weight - weight)
