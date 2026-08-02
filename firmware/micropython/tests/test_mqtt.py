import json

import pytest

MqttTracer = __import__("src.mqtt_adapter", None, None, ("MqttTracer",)).MqttTracer


class ConnectedEthernet:
    def status(self):
        return {"link_up": True}


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
    tracer = MqttTracer(
        config(),
        ConnectedEthernet(),
        client_factory=lambda **_kwargs: client,
        clock_ms=lambda: 123,
    )
    tracer.poll()
    assert client.callback is not None
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
        ConnectedEthernet(),
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

    tracer = MqttTracer(config(), ConnectedEthernet(), client_factory=unavailable_client)

    tracer.poll()

    assert tracer.client is None
    assert tracer.last_error == "MQTT_CONNECT_FAILED: connection refused"
