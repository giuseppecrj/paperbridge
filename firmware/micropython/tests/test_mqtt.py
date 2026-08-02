import json

import pytest

MqttTracer = __import__("src.mqtt_adapter", None, None, ("MqttTracer",)).MqttTracer


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
        },
    }


def connected_tracer():
    client = FakeClient()
    wifi = ConnectedWiFi()
    tracer = MqttTracer(
        config(),
        wifi,
        client_factory=lambda **_kwargs: client,
        clock_ms=lambda: 123,
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
    assert client.subscriptions == [(b"v1/devices/paperbridge-dev-001/jobs", 1)]
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
    assert second.subscriptions == [(b"v1/devices/paperbridge-dev-001/jobs", 1)]


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
