from __future__ import annotations

import pytest

from pii_guard.core.codec import decode_record, encode_record
from pii_guard.core.models import MappingRecord, Replacement


def _record() -> MappingRecord:
    return MappingRecord(
        original_fp="a1b2c3",
        masked_text="Имя И. И., тел. 45** ****56, почта п@домен.рф 🚀",
        replacements=(
            Replacement(0, 9, 0, "Иванов Иван", "И. И.", "PERSON"),
            Replacement(15, 25, 15, "4509 123456", "45** ****56", "PHONE"),
            Replacement(32, 44, 32, "почта@домен.рф", "п@домен.рф", "EMAIL"),
        ),
    )


def test_roundtrip_with_cyrillic_and_emoji() -> None:
    record = _record()
    decoded = decode_record(encode_record(record))
    assert decoded == record


def test_roundtrip_empty_replacements() -> None:
    record = MappingRecord(original_fp="fp", masked_text="текст без ПД", replacements=())
    assert decode_record(encode_record(record)) == record


@pytest.mark.parametrize(
    "data",
    [
        b"not json",
        b"{}",
        b'{"f": "x"}',
        b'{"f": "x", "m": "y", "r": [[0, 1]]}',
        b'{"f": "x", "m": "y", "r": "bad"}',
        b'{"f": "x", "m": "y", "r": [[0, 1, 2, "a", "b", "c", "extra"]]}',
    ],
)
def test_decode_invalid_data_raises_value_error(data: bytes) -> None:
    with pytest.raises(ValueError):
        decode_record(data)
