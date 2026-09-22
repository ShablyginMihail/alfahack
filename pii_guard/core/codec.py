from __future__ import annotations

import orjson

from pii_guard.core.models import MappingRecord, Replacement


def encode_record(record: MappingRecord) -> bytes:
    replacements = [
        [
            r.start,
            r.end,
            r.masked_start,
            r.original,
            r.masked,
            r.pii_type,
        ]
        for r in record.replacements
    ]
    payload = {
        "f": record.original_fp,
        "m": record.masked_text,
        "r": replacements,
    }
    return orjson.dumps(payload)


def decode_record(data: bytes) -> MappingRecord:
    try:
        payload = orjson.loads(data)
        if not isinstance(payload, dict):
            raise ValueError
        original_fp = payload["f"]
        masked_text = payload["m"]
        raw_replacements = payload["r"]
        if not isinstance(original_fp, str) or not isinstance(masked_text, str):
            raise ValueError
        if not isinstance(raw_replacements, list):
            raise ValueError
        replacements = tuple(_decode_replacement(item) for item in raw_replacements)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("invalid mapping record") from exc
    return MappingRecord(
        original_fp=original_fp,
        masked_text=masked_text,
        replacements=replacements,
    )


def _decode_replacement(item: object) -> Replacement:
    if not isinstance(item, list) or len(item) != 6:
        raise ValueError
    start, end, masked_start, original, masked, pii_type = item
    if not all(isinstance(v, int) for v in (start, end, masked_start)):
        raise ValueError
    if not all(isinstance(v, str) for v in (original, masked, pii_type)):
        raise ValueError
    return Replacement(
        start=start,
        end=end,
        masked_start=masked_start,
        original=original,
        masked=masked,
        pii_type=pii_type,
    )
