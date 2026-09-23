from __future__ import annotations

import re
import threading
import time
from collections.abc import Sequence

import structlog

from pii_guard.core.models import Span
from pii_guard.core.normalize import Document
from pii_guard.core.registry import Recognizer
from pii_guard.core.service_words import SERVICE_WORDS
from pii_guard.observability.metrics import observe_ner

logger = structlog.get_logger()

_WORD_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*")

_WARM_UP_TEXT = "Иванов Иван Иванович, Москва, ул. Ленина"


class MlStage:
    def __init__(
        self,
        recognizer: Recognizer,
        max_chars: int = 2000,
        concurrency: int = 1,
        wait_ms: int = 20,
    ) -> None:
        self._recognizer = recognizer
        self._max_chars = max_chars
        self._semaphore = threading.BoundedSemaphore(concurrency)
        self._wait_ms = wait_ms
        self._disabled = False

    def run(self, doc: Document, rule_candidates: Sequence[Span]) -> list[Span]:
        if self._disabled:
            observe_ner("unavailable", 0.0)
            return []
        if len(doc.text) > self._max_chars:
            observe_ner("long", 0.0)
            return []
        if self._covered(doc, rule_candidates):
            observe_ner("covered", 0.0)
            return []
        if not self._semaphore.acquire(timeout=self._wait_ms / 1000):
            observe_ner("busy", 0.0)
            return []
        try:
            start = time.perf_counter()
            try:
                spans = list(self._recognizer.find(doc))
            except Exception as exc:
                duration = time.perf_counter() - start
                observe_ner("error", duration)
                logger.warning(
                    "recognizer_failed",
                    recognizer=self._recognizer.name,
                    error_type=type(exc).__name__,
                )
                return []
            duration = time.perf_counter() - start
            observe_ner("ok", duration)
            return self._vote(spans, rule_candidates)
        finally:
            self._semaphore.release()

    def warm_up(self) -> None:
        if self._disabled:
            return
        doc = Document.from_text(_WARM_UP_TEXT)
        try:
            list(self._recognizer.find(doc))
        except Exception as exc:
            self._disabled = True
            logger.warning(
                "recognizer_failed",
                recognizer=self._recognizer.name,
                error_type=type(exc).__name__,
            )

    @staticmethod
    def _covered(doc: Document, rule_candidates: Sequence[Span]) -> bool:
        chars = list(doc.norm)
        for span in rule_candidates:
            if (
                span.score >= 0.5
                and span.start < span.end
                and span.start >= 0
                and span.end <= len(doc.norm)
            ):
                for i in range(span.start, span.end):
                    chars[i] = " "
        for word in _WORD_RE.findall("".join(chars)):
            letters = sum(1 for ch in word if ch.isalpha())
            if letters >= 2 and word not in SERVICE_WORDS:
                return False
        return True

    @staticmethod
    def _overlaps(a: Span, b: Span) -> bool:
        return a.start < b.end and b.start < a.end

    def _vote(self, spans: list[Span], rule_candidates: Sequence[Span]) -> list[Span]:
        result: list[Span] = []
        for span in spans:
            if any(
                cand.pii_type != span.pii_type and cand.score >= 0.5 and self._overlaps(span, cand)
                for cand in rule_candidates
            ):
                continue
            score = span.score
            for cand in rule_candidates:
                if (
                    cand.pii_type == span.pii_type
                    and cand.score >= 0.2
                    and self._overlaps(span, cand)
                ):
                    score = min(1.0, score + 0.2)
                    break
            if score != span.score:
                span = Span(
                    span.start,
                    span.end,
                    span.pii_type,
                    score,
                    span.recognizer,
                    span.part,
                )
            result.append(span)
        return result
