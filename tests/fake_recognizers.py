from __future__ import annotations

import re

from pii_guard.core.models import Span
from pii_guard.core.normalize import Document

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PASSPORT_RE = re.compile(r"\b4509 123456\b")


class FakeRecognizer:
    name = "fake"
    pii_types = frozenset({"EMAIL", "PASSPORT"})

    def find(self, doc: Document) -> list[Span]:
        spans: list[Span] = []
        for match in EMAIL_RE.finditer(doc.text):
            spans.append(
                Span(
                    start=match.start(),
                    end=match.end(),
                    pii_type="EMAIL",
                    score=1.0,
                    recognizer=self.name,
                )
            )
        for match in PASSPORT_RE.finditer(doc.text):
            spans.append(
                Span(
                    start=match.start(),
                    end=match.end(),
                    pii_type="PASSPORT",
                    score=1.0,
                    recognizer=self.name,
                )
            )
        return spans


class FailingRecognizer:
    name = "failing"
    pii_types = frozenset({"EMAIL"})

    def find(self, doc: Document) -> list[Span]:
        raise RuntimeError("boom")


def recognizers() -> list[FakeRecognizer]:
    return [FakeRecognizer()]
