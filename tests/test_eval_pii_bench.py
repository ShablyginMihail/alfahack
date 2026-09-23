import pytest

from eval.pii_bench_metrics import (
    Entity,
    aggregate_domain_docs,
    aggregate_entity_docs,
    entity_status,
    parse_entities,
    time_stats,
    wilson_interval,
)

CLOSED = "closed"
PARTIAL = "partial"
MISSED = "missed"

NAME_TEXT = "Иванов Иван"
NAME_START = 0
NAME_END = 11

ADDRESS_TEXT = "г. Москва, ул. Ленина"
ADDRESS_START = 3
ADDRESS_END = 21
ADDRESS_SIGNIFICANT = set(range(3, 9)) | set(range(15, 21))


def test_entity_status_closed() -> None:
    masked = set(range(NAME_START, NAME_END))
    assert entity_status(NAME_TEXT, NAME_START, NAME_END, masked) == CLOSED


def test_entity_status_partial() -> None:
    masked = set(range(NAME_START, 6))
    assert entity_status(NAME_TEXT, NAME_START, NAME_END, masked) == PARTIAL


def test_entity_status_missed() -> None:
    assert entity_status(NAME_TEXT, NAME_START, NAME_END, set()) == MISSED


def test_entity_status_service_word_ignored() -> None:
    masked = set(range(ADDRESS_START, ADDRESS_END))
    assert entity_status(ADDRESS_TEXT, ADDRESS_START, ADDRESS_END, masked) == CLOSED


def test_entity_status_service_word_not_required() -> None:
    assert entity_status(ADDRESS_TEXT, ADDRESS_START, ADDRESS_END, ADDRESS_SIGNIFICANT) == CLOSED


def test_entity_status_no_significant_chars() -> None:
    assert entity_status("ул.", 0, 3, set()) == CLOSED


def test_wilson_interval_zero_n() -> None:
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_wilson_interval_known() -> None:
    lo, hi = wilson_interval(5, 10)
    assert lo == pytest.approx(0.237, abs=0.001)
    assert hi == pytest.approx(0.763, abs=0.001)


def test_parse_entities_from_json_string() -> None:
    value = f'[{{"start": {NAME_START}, "end": {NAME_END}, "type": "NAME", "text": "{NAME_TEXT}"}}]'
    assert parse_entities(value) == [Entity(NAME_START, NAME_END, "NAME", NAME_TEXT)]


def test_parse_entities_from_list() -> None:
    value = [{"start": NAME_START, "end": NAME_END, "type": "NAME", "text": NAME_TEXT}]
    assert parse_entities(value) == [Entity(NAME_START, NAME_END, "NAME", NAME_TEXT)]


def test_parse_entities_none() -> None:
    assert parse_entities(None) == []


def test_aggregate_entity_docs() -> None:
    entity = Entity(NAME_START, NAME_END, "NAME", NAME_TEXT)
    per_type, leak, total = aggregate_entity_docs(
        [([entity], [CLOSED]), ([entity], [PARTIAL]), ([entity], [MISSED])]
    )
    assert per_type == {"NAME": {"closed": 1, "partial": 1, "missed": 1}}
    assert leak == 2
    assert total == 3


def test_aggregate_domain_docs() -> None:
    fp, total = aggregate_domain_docs([True, False, True])
    assert fp == 2
    assert total == 3


def test_time_stats() -> None:
    mean, p95 = time_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert mean == pytest.approx(3.0)
    assert p95 == pytest.approx(5.0)


def test_time_stats_empty() -> None:
    assert time_stats([]) == (0.0, 0.0)
