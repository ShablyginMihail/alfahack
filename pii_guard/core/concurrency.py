from __future__ import annotations


class ConcurrencyGate:
    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._count = 0

    def try_enter(self) -> bool:
        if self._count >= self._limit:
            return False
        self._count += 1
        return True

    def exit(self) -> None:
        if self._count > 0:
            self._count -= 1
