from __future__ import annotations

import hmac
import time
from dataclasses import dataclass

from pii_guard.config.loader import ConfigStore
from pii_guard.core.demasking import unmask
from pii_guard.core.engine import Engine
from pii_guard.core.models import MappingRecord
from pii_guard.core.policy import CHECKER_PROFILE, Profile
from pii_guard.observability.metrics import observe_entities, observe_stage, observe_tokens
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
        config_store: ConfigStore,
        store: MappingStore,
        cipher: RecordCipher,
        ttl_seconds: int,
    ) -> None:
        self._config_store = config_store
        self._store = store
        self._cipher = cipher
        self._ttl_seconds = ttl_seconds

    async def handle(self, payload_id: str, payload: str) -> ProcessOutcome:
        config, engine = self._config_store.current()
        profile = config.profiles().get("checker", CHECKER_PROFILE)
        observe_tokens("/process", payload)
        record = await self._store_get(payload_id)
        if record is None:
            return await self._mask(engine, profile, payload_id, payload)

        if hmac.compare_digest(self._cipher.fingerprint(payload), record.original_fp):
            return ProcessOutcome(
                result=record.masked_text,
                direction="mask_retry",
                type_counts=self._counts(record),
            )

        if payload == record.masked_text:
            return self._unmask(profile, record, payload, "unmask")

        return self._unmask(profile, record, payload, "unmask_changed")

    async def _store_get(self, key: str) -> MappingRecord | None:
        start = time.perf_counter()
        try:
            return await self._store.get(key)
        finally:
            observe_stage("store_get", time.perf_counter() - start)

    async def _mask(
        self, engine: Engine, profile: Profile, payload_id: str, payload: str
    ) -> ProcessOutcome:
        start = time.perf_counter()
        masked = engine.mask(payload, profile)
        observe_stage("detect_mask", time.perf_counter() - start)
        record = MappingRecord(
            original_fp=self._cipher.fingerprint(payload),
            masked_text=masked.text,
            replacements=masked.replacements,
        )
        start = time.perf_counter()
        stored = await self._store.put_if_absent(payload_id, record, self._ttl_seconds)
        observe_stage("store_put", time.perf_counter() - start)
        observe_entities("checker", self._counts(stored).items())
        return ProcessOutcome(
            result=stored.masked_text,
            direction="mask",
            type_counts=self._counts(stored),
        )

    def _unmask(
        self, profile: Profile, record: MappingRecord, payload: str, direction: str
    ) -> ProcessOutcome:
        if not profile.unmask:
            return ProcessOutcome(
                result=payload,
                direction="unmask_denied",
                type_counts=self._counts(record),
            )
        start = time.perf_counter()
        result = unmask(payload, record)
        observe_stage("unmask", time.perf_counter() - start)
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
