import json
import threading
from pathlib import Path

import pytest
from src.escpos import EscPosRenderer
from src.print_coordinator import PrintCoordinator
from src.printer_transport import TransportError
from src.serial_rpc import RpcError

JobService = __import__("src.job_service", None, None, ("JobService",)).JobService

FIXTURES = Path("packages/protocol/fixtures/print-job-v1")


def load(name):
    return json.loads((FIXTURES / name).read_text())


class FakeCoordinator:
    def __init__(self):
        self.calls = []

    def print_job(self, job, allow_cut=False):
        self.calls.append((job, allow_cut))
        return {
            "job_id": job["job_id"],
            "status": "delivered_to_printer",
            "bytes_sent": 28,
        }


def service():
    coordinator = FakeCoordinator()
    return JobService({"device_id": "paperbridge-dev-001"}, coordinator), coordinator


def test_submits_a_valid_job_through_the_shared_coordinator():
    instance, coordinator = service()
    job = load("valid-text-feed.json")

    assert instance.submit(job) == {
        "job_id": "job-hello-001",
        "status": "delivered_to_printer",
        "bytes_sent": 28,
    }
    assert coordinator.calls == [(job, False)]


@pytest.mark.parametrize(
    ("job", "allow_cut", "code"),
    [
        (load("invalid-fractional-feed.json"), False, "INVALID_PRINT_JOB"),
        ({**load("valid-text-feed.json"), "device_id": "other-device"}, False, "WRONG_DEVICE"),
        (load("valid-cut.json"), False, "UNAUTHORIZED_CUT"),
    ],
)
def test_rejects_invalid_wrong_device_and_unauthorized_cut(job, allow_cut, code):
    instance, coordinator = service()

    with pytest.raises(RpcError) as error:
        instance.submit(job, allow_cut=allow_cut)

    assert error.value.code == code
    assert coordinator.calls == []


def test_preserves_partial_write_bytes_for_correlated_failure_results():
    class PartialTransport:
        def send(self, _payload):
            raise TransportError("PRINTER_CONNECTION_RESET", "reset", bytes_sent=2)

    instance = JobService(
        {"device_id": "paperbridge-dev-001"},
        PrintCoordinator(EscPosRenderer(), PartialTransport()),
    )

    with pytest.raises(RpcError) as error:
        instance.submit(load("valid-text-feed.json"))

    assert error.value.code == "PRINTER_CONNECTION_RESET"
    assert error.value.bytes_sent == 2


def test_serializes_usb_and_mqtt_delivery_through_the_shared_service():
    first_inside = threading.Event()
    second_attempting = threading.Event()
    release_first = threading.Event()
    second_done = threading.Event()
    active = 0
    maximum_active = 0
    state_lock = threading.Lock()

    class BlockingTransport:
        def __init__(self):
            self.calls = 0

        def send(self, payload):
            nonlocal active, maximum_active
            with state_lock:
                self.calls += 1
                first_call = self.calls == 1
                active += 1
                maximum_active = max(maximum_active, active)
            if first_call:
                first_inside.set()
                assert release_first.wait(1)
            with state_lock:
                active -= 1
            return {"status": "delivered_to_printer", "bytes_sent": len(payload)}

    coordinator = PrintCoordinator(EscPosRenderer(), BlockingTransport())
    instance = JobService({"device_id": "paperbridge-dev-001"}, coordinator)
    first_job = load("valid-text-feed.json")
    second_job = {**first_job, "job_id": "job-second"}
    first = threading.Thread(target=instance.submit, args=(first_job,))

    def submit_second():
        second_attempting.set()
        instance.submit(second_job)
        second_done.set()

    second = threading.Thread(target=submit_second)
    first.start()
    try:
        assert first_inside.wait(1)
        second.start()
        assert second_attempting.wait(1)
        assert not second_done.wait(0.05)
    finally:
        release_first.set()
        first.join(1)
        second.join(1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert maximum_active == 1


def test_device_policy_can_authorize_a_schema_valid_cut():
    instance, coordinator = service()
    job = load("valid-cut.json")

    instance.submit(job, allow_cut=True)

    assert coordinator.calls == [(job, True)]
