from __future__ import annotations

import hmac
from dataclasses import dataclass

from pii_guard.core.demasking import unmask
from pii_guard.core.engine import Engine
from pii_guard.core.models import MappingRecord
from pii_guard.core.policy import Profile
from pii_guard.store.base import MappingStore
from pii_guard.store.crypto import RecordCipher


@dataclass(frozen=True, slots=True)
class ProcessOutcome:
    result: str
    direction: str
    type_counts: dict[str, int]


class ProcessService:
    def __init__(
        self,
        engine: Engine,
        store: MappingStore,
        cipher: RecordCipher,
        profile: Profile,
        ttl_seconds: int,
    ) -> None:
        self._engine = engine
        self._store = store
        self._cipher = cipher
        self._profile = profile
        self._ttl_seconds = ttl_seconds

    async def handle(self, payload_id: str, payload: str) -> ProcessOutcome:
        record = await self._store.get(payload_id)
        if record is None:
            return await self._mask(payload_id, payload)

        if hmac.compare_digest(self._cipher.fingerprint(payload), record.original_fp):
            return ProcessOutcome(
                result=record.masked_text,
                direction="mask_retry",
                type_counts=self._counts(record),
            )

        if payload == record.masked_text:
            return self._unmask(record, payload, "unmask")

        return self._unmask(record, payload, "unmask_changed")

    async def _mask(self, payload_id: str, payload: str) -> ProcessOutcome:
        masked = self._engine.mask(payload, self._profile)
        record = MappingRecord(
            original_fp=self._cipher.fingerprint(payload),
            masked_text=masked.text,
            replacements=masked.replacements,
        )
        stored = await self._store.put_if_absent(payload_id, record, self._ttl_seconds)
        return ProcessOutcome(
            result=stored.masked_text,
            direction="mask",
            type_counts=self._counts(stored),
        )

    def _unmask(self, record: MappingRecord, payload: str, direction: str) -> ProcessOutcome:
        if not self._profile.unmask:
            return ProcessOutcome(
                result=payload,
                direction="unmask_denied",
                type_counts=self._counts(record),
            )
        result = unmask(payload, record)
        return ProcessOutcome(
            result=result,
            direction=direction,
            type_counts=self._counts(record),
        )

    @staticmethod
    def _counts(record: MappingRecord) -> dict[str, int]:
        counts: dict[str, int] = {}
        for replacement in record.replacements:
            counts[replacement.pii_type] = counts.get(replacement.pii_type, 0) + 1
        return counts
