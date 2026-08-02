import json
from pathlib import Path

import pytest
from src.escpos import EscPosRenderer
from src.job_ledger import JobLedger
from src.print_coordinator import PrintCoordinator
from src.serial_rpc import RpcError

JobService = __import__("src.job_service", None, None, ("JobService",)).JobService
MqttTracer = __import__("src.mqtt_adapter", None, None, ("MqttTracer",)).MqttTracer

FIXTURES = Path("packages/protocol/fixtures/print-job-v1")


class ConnectedWiFi:
    def __init__(self, connected=True):
        self.connected = connected
        self.poll_calls = 0

    def poll(self):
        self.poll_calls += 1

    def status(self):
        return {"connected": self.connected}


class TrackingLock:
    def __init__(self):
        self.acquires = 0
        self.depth = 0

    def acquire(self):
        self.acquires += 1
        self.depth += 1

    def release(self):
        self.depth -= 1


class FakeJobService:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "job_id": "job-hello-001",
            "status": "delivered_to_printer",
            "bytes_sent": 28,
        }
        self.error = error
        self.calls = []

    def submit(self, job, allow_cut=False):
        self.calls.append((job, allow_cut))
        if self.error is not None:
            raise self.error
        return self.result


class RecordingTransport:
    def __init__(self):
        self.payloads = []

    def send(self, payload):
        self.payloads.append(payload)
        return {"status": "delivered_to_printer", "bytes_sent": len(payload)}


class FakeClient:
    def __init__(self):
        self.callback = None
        self.connected = False
        self.subscriptions = []
        self.published = []

    def set_callback(self, callback):
        self.callback = callback

    def connect(self):
        self.connected = True

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))

    def check_msg(self):
        return None

    def publish(self, topic, payload, qos=0, retain=False):
        self.published.append((topic, json.loads(payload), qos, retain))


def config():
    return {
        "device_id": "paperbridge-dev-001",
        "mqtt": {
            "host": "192.0.2.1",
            "port": 1883,
            "client_id": "paperbridge-dev-001",
            "username": "paperbridge-dev-001",
            "password": "not-a-real-secret",
            "keepalive_seconds": 30,
            "retry_interval_ms": 1000,
            "max_message_bytes": 1024,
            "topic_prefix": "v1/devices",
            "allow_cut": False,
        },
    }


def connected_tracer(job_service=None, job_ledger=None, settings=None):
    client = FakeClient()
    wifi = ConnectedWiFi()
    tracer = MqttTracer(
        settings or config(),
        wifi,
        client_factory=lambda **_kwargs: client,
        clock_ms=lambda: 123,
        job_service=job_service,
        job_ledger=job_ledger,
    )
    tracer.poll()
    assert client.callback is not None
    assert wifi.poll_calls == 1
    return tracer, client


def test_tracer_returns_correlated_probe_after_connecting():
    tracer, client = connected_tracer()
    callback = client.callback
    assert callback is not None
    callback(
        b"v1/devices/paperbridge-dev-001/jobs",
        (
            b'{"schema_version":1,"kind":"mqtt_probe","probe_id":"probe-001",'
            b'"device_id":"paperbridge-dev-001","created_at":"2026-08-02T00:00:00Z"}'
        ),
    )

    assert client.connected is True
    assert client.subscriptions == [
        (b"v1/devices/paperbridge-dev-001/jobs", 1),
        (b"v1/devices/paperbridge-dev-001/print-jobs", 1),
    ]
    assert client.published == [
        (
            b"v1/devices/paperbridge-dev-001/status",
            {
                "schema_version": 1,
                "kind": "mqtt_probe_status",
                "probe_id": "probe-001",
                "device_id": "paperbridge-dev-001",
                "status": "ok",
                "ts_ms": 123,
            },
            1,
            False,
        )
    ]


@pytest.mark.parametrize(
    ("topic", "payload", "error"),
    [
        (b"v1/devices/paperbridge-dev-001/events", b"{}", "UNEXPECTED_MQTT_TOPIC"),
        (
            b"v1/devices/paperbridge-dev-001/jobs",
            b'{"schema_version":1,"kind":"mqtt_probe","probe_id":"probe-001",'
            b'"device_id":"other-device","created_at":"2026-08-02T00:00:00Z"}',
            "INVALID_MQTT_PROBE",
        ),
        (b"v1/devices/paperbridge-dev-001/jobs", b"not-json", "INVALID_MQTT_PAYLOAD"),
        (b"v1/devices/paperbridge-dev-001/jobs", b"x" * 1025, "INVALID_MQTT_PAYLOAD"),
    ],
)
def test_tracer_rejects_invalid_messages_without_publishing(topic, payload, error):
    tracer, client = connected_tracer()
    callback = client.callback
    assert callback is not None

    callback(topic, payload)

    assert client.published == []
    assert tracer.last_error == error


def test_mqtt_job_returns_a_correlated_terminal_result():
    service = FakeJobService()
    tracer, client = connected_tracer(service, JobLedger(max_completed_ids=2))
    callback = client.callback
    assert callback is not None
    job = json.loads((FIXTURES / "valid-text-feed.json").read_text())

    callback(
        b"v1/devices/paperbridge-dev-001/print-jobs",
        json.dumps(job).encode(),
    )

    assert service.calls == [(job, False)]
    assert client.published[-1] == (
        b"v1/devices/paperbridge-dev-001/job-results",
        {
            "schema_version": "1",
            "kind": "job_result",
            "job_id": "job-hello-001",
            "device_id": "paperbridge-dev-001",
            "status": "delivered_to_printer",
            "bytes_sent": 28,
        },
        1,
        False,
    )


def test_qos_redelivery_replays_the_result_without_a_second_printer_delivery():
    settings = config()
    transport = RecordingTransport()
    service = JobService(settings, PrintCoordinator(EscPosRenderer(), transport))
    tracer, client = connected_tracer(service, JobLedger(max_completed_ids=2), settings)
    callback = client.callback
    assert callback is not None
    payload = (FIXTURES / "valid-text-feed.json").read_bytes()

    callback(b"v1/devices/paperbridge-dev-001/print-jobs", payload)
    callback(b"v1/devices/paperbridge-dev-001/print-jobs", payload)

    assert transport.payloads == [b"\x1b@Hello from Paperbridge\n\n\n\n"]
    assert client.published[-1] == client.published[-2]


def test_mqtt_job_reports_partial_delivery_and_preserves_bytes_sent():
    service = FakeJobService(
        error=RpcError(
            "PRINTER_CONNECTION_RESET",
            "Printer closed during write",
            bytes_sent=2,
        )
    )
    tracer, client = connected_tracer(service, JobLedger(max_completed_ids=2))
    callback = client.callback
    assert callback is not None

    callback(
        b"v1/devices/paperbridge-dev-001/print-jobs",
        (FIXTURES / "valid-text-feed.json").read_bytes(),
    )

    assert client.published[-1][1] == {
        "schema_version": "1",
        "kind": "job_result",
        "job_id": "job-hello-001",
        "device_id": "paperbridge-dev-001",
        "status": "failed",
        "error_code": "PRINTER_CONNECTION_RESET",
        "bytes_sent": 2,
    }


def test_unrecognized_device_errors_are_normalized_to_stable_internal_error():
    service = FakeJobService(error=RpcError("NOT_A_STABLE_CODE", "boom"))
    tracer, client = connected_tracer(service, JobLedger(max_completed_ids=2))
    callback = client.callback
    assert callback is not None

    callback(
        b"v1/devices/paperbridge-dev-001/print-jobs",
        (FIXTURES / "valid-text-feed.json").read_bytes(),
    )

    assert client.published[-1][1]["status"] == "failed"
    assert client.published[-1][1]["error_code"] == "INTERNAL_ERROR"


def test_mqtt_cut_policy_defaults_to_rejected_without_client_override():
    service = FakeJobService(error=RpcError("UNAUTHORIZED_CUT", "cut is disabled"))
    tracer, client = connected_tracer(service, JobLedger(max_completed_ids=2))
    callback = client.callback
    assert callback is not None

    callback(
        b"v1/devices/paperbridge-dev-001/print-jobs",
        (FIXTURES / "valid-cut.json").read_bytes(),
    )

    assert service.calls[0][1] is False
    assert client.published[-1][1]["status"] == "rejected"
    assert client.published[-1][1]["error_code"] == "UNAUTHORIZED_CUT"


def test_mqtt_cut_policy_can_be_enabled_only_by_device_configuration():
    settings = config()
    settings["mqtt"]["allow_cut"] = True
    service = FakeJobService()
    tracer, client = connected_tracer(service, JobLedger(max_completed_ids=2), settings)
    callback = client.callback
    assert callback is not None

    callback(
        b"v1/devices/paperbridge-dev-001/print-jobs",
        (FIXTURES / "valid-cut.json").read_bytes(),
    )

    assert service.calls[0][1] is True


def test_tracer_marks_mqtt_unavailable_when_wifi_disconnects():
    tracer, _client = connected_tracer()
    tracer.wifi.connected = False

    tracer.poll()

    assert tracer.status() == {
        "enabled": True,
        "connected": False,
        "last_error": "WIFI_DISCONNECTED",
    }


def test_tracer_reconnects_and_resubscribes_after_a_poll_failure():
    class FailingClient(FakeClient):
        def check_msg(self):
            raise OSError("connection reset")

    now = [0]
    first = FailingClient()
    second = FakeClient()
    clients = [first, second]
    tracer = MqttTracer(
        config(),
        ConnectedWiFi(),
        client_factory=lambda **_kwargs: clients.pop(0),
        clock_ms=lambda: now[0],
    )

    tracer.poll()
    tracer.poll()
    now[0] = 1000
    tracer.poll()

    assert tracer.client is second
    assert second.subscriptions == [
        (b"v1/devices/paperbridge-dev-001/jobs", 1),
        (b"v1/devices/paperbridge-dev-001/print-jobs", 1),
    ]


def test_tracer_records_broker_connection_failure():
    def unavailable_client(**_kwargs):
        raise OSError("connection refused")

    tracer = MqttTracer(config(), ConnectedWiFi(), client_factory=unavailable_client)

    tracer.poll()

    assert tracer.client is None
    assert tracer.last_error == "MQTT_CONNECT_FAILED: connection refused"


def test_broker_retry_timing_is_safe_across_wrapped_device_ticks():
    now = [1000]
    differences = []
    attempts = []

    def unavailable_client(**_kwargs):
        attempts.append(True)
        raise OSError("connection refused")

    def ticks_diff(new, old):
        differences.append((new, old))
        return 1000

    tracer = MqttTracer(
        config(),
        ConnectedWiFi(),
        client_factory=unavailable_client,
        clock_ms=lambda: now[0],
        ticks_diff=ticks_diff,
    )
    tracer.poll()
    now[0] = 5
    tracer.poll()

    assert differences == [(5, 1000)]
    assert len(attempts) == 2


def test_status_reads_mqtt_state_under_lock():
    lock = TrackingLock()
    tracer = MqttTracer(config(), ConnectedWiFi(), lock=lock)

    assert tracer.status()["connected"] is False
    assert lock.acquires == 1
    assert lock.depth == 0


def test_tracer_does_not_connect_before_wifi_has_an_address():
    client = FakeClient()
    wifi = ConnectedWiFi(connected=False)
    tracer = MqttTracer(config(), wifi, client_factory=lambda **_kwargs: client)

    tracer.poll()

    assert wifi.poll_calls == 1
    assert tracer.client is None
    assert client.connected is False
