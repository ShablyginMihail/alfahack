from __future__ import annotations

from tests.fake_recognizers import FailingRecognizer


def recognizers() -> list[FailingRecognizer]:
    return [FailingRecognizer()]
