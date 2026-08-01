import pytest
from src.status import StatusTracker


def test_delivery_transition_uses_delivered_not_printed():
    tracker = StatusTracker()
    for status in (
        "validated",
        "rendering",
        "connecting_to_printer",
        "sending_to_printer",
        "delivered_to_printer",
    ):
        tracker.transition(status)
    assert tracker.current == "delivered_to_printer"


def test_invalid_transition_is_rejected():
    with pytest.raises(ValueError):
        StatusTracker().transition("delivered_to_printer")
