from eval.generate import ALL_TYPES, Generator
from eval.markup import parse_markup
from pii_guard.recognizers.validators import digits, inn_valid, luhn_valid, snils_valid


def test_deterministic() -> None:
    assert Generator(42).generate(5) == Generator(42).generate(5)


def test_parseable() -> None:
    for line in Generator(42).generate(5):
        if line.startswith("#") or not line.strip():
            continue
        parse_markup(line)


def test_all_types_present() -> None:
    lines = Generator(42).generate(5)
    types: set[str] = set()
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        _, spans = parse_markup(line)
        types.update(s.pii_type for s in spans)
    assert types == set(ALL_TYPES)


def test_traps_have_no_spans() -> None:
    lines = Generator(42).generate(5)
    category = "general"
    for line in lines:
        if line.startswith("#"):
            category = line[1:].strip().lower()
            continue
        if category == "traps":
            _, spans = parse_markup(line)
            assert spans == []


def test_validators() -> None:
    for line in Generator(42).generate(5):
        if line.startswith("#") or not line.strip():
            continue
        text, spans = parse_markup(line)
        for span in spans:
            value = text[span.start : span.end]
            if span.pii_type == "INN":
                assert inn_valid(digits(value))
            elif span.pii_type == "CARD_NUMBER":
                assert luhn_valid(digits(value))
            elif span.pii_type == "SNILS":
                assert snils_valid(digits(value))
