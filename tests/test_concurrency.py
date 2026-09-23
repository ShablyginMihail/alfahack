from pii_guard.core.concurrency import ConcurrencyGate


def test_first_request_passes_any_weight() -> None:
    gate = ConcurrencyGate(limit=2, max_weight=100)
    assert gate.try_enter(weight=200) is True


def test_second_request_rejected_on_weight() -> None:
    gate = ConcurrencyGate(limit=2, max_weight=100)
    assert gate.try_enter(weight=80) is True
    assert gate.try_enter(weight=30) is False


def test_weight_released_after_exit() -> None:
    gate = ConcurrencyGate(limit=2, max_weight=100)
    assert gate.try_enter(weight=80) is True
    assert gate.try_enter(weight=30) is False
    gate.exit(weight=80)
    assert gate.try_enter(weight=30) is True


def test_limit_by_count_unchanged() -> None:
    gate = ConcurrencyGate(limit=2, max_weight=1000)
    assert gate.try_enter() is True
    assert gate.try_enter() is True
    assert gate.try_enter() is False
    gate.exit()
    assert gate.try_enter() is True
    assert gate.try_enter() is False
