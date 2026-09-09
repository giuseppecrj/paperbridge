import builtins
import json
import types
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

    def submit(self, job, allow_cut=False, before_delivery=None):
        self.calls.append((job, allow_cut))
        if before_delivery is not None:
            before_delivery()
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
            "max_message_bytes": 65_536,
            "topic_prefix": "v1/devices",
            "allow_cut": False,
        },
    }


def connected_tracer(job_service=None, job_ledger=None, settings=None, before_delivery=None):
    client = FakeClient()
    wifi = ConnectedWiFi()
    tracer = MqttTracer(
        settings or config(),
        wifi,
        client_factory=lambda **_kwargs: client,
        clock_ms=lambda: 123,
        job_service=job_service,
        job_ledger=job_ledger,
        before_delivery=before_delivery,
    )
    tracer.poll()
    assert client.callback is not None
    assert wifi.poll_calls == 1
    return tracer, client


def test_default_tls_client_factory_uses_ca_verification_and_sni(monkeypatch):
    captured = {}

    def mqtt_client(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return object()

    original_import = builtins.__import__
    from src import mqtt_client as bundled_mqtt

    monkeypatch.setattr(bundled_mqtt, "MQTTClient", mqtt_client)
    modules = {
        "ssl": types.SimpleNamespace(CERT_REQUIRED="required"),
    }
    monkeypatch.setattr(
        builtins,
        "__import__",
        lambda name, *args, **kwargs: modules.get(name) or original_import(name, *args, **kwargs),
    )

    MqttTracer._default_client_factory(
        client_id="paperbridge-dev-001",
        host="abc.emqxsl.com",
        port=8883,
        username="device",
        password="password",
        keepalive_seconds=30,
        max_message_bytes=65_536,
        max_topic_bytes=47,
        tls={
            "enabled": True,
            "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
            "server_hostname": "abc.emqxsl.com",
        },
    )

    assert captured == {
        "args": ("paperbridge-dev-001", "abc.emqxsl.com"),
        "kwargs": {
            "port": 8883,
            "user": "device",
            "password": "password",
            "keepalive": 30,
            "max_message_bytes": 65_536,
            "max_topic_bytes": 47,
            "ssl": True,
            "ssl_params": {
                "cert_reqs": "required",
                "cadata": b"-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
                "server_hostname": "abc.emqxsl.com",
            },
        },
    }


def test_tls_client_factory_receives_required_ca_verification_and_sni():
    settings = config()
    settings["mqtt"]["tls"] = {
        "enabled": True,
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
        "server_hostname": "abc.emqxsl.com",
    }
    received = {}
    client = FakeClient()
    tracer = MqttTracer(
        settings,
        ConnectedWiFi(),
        client_factory=lambda **kwargs: (received.update(kwargs) or client),
        utc_year=lambda: 2026,
    )

    tracer.poll()

    assert received == {
        "client_id": "paperbridge-dev-001",
        "host": "192.0.2.1",
        "port": 1883,
        "username": "paperbridge-dev-001",
        "password": "not-a-real-secret",
        "keepalive_seconds": 30,
        "max_message_bytes": 65_536,
        "max_topic_bytes": len(b"v1/devices/paperbridge-dev-001/print-jobs"),
        "tls": {
            "enabled": True,
            "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
            "server_hostname": "abc.emqxsl.com",
        },
    }
    assert client.subscriptions == [
        (b"v1/devices/paperbridge-dev-001/jobs", 1),
        (b"v1/devices/paperbridge-dev-001/print-jobs", 1),
    ]


def test_tls_syncs_time_before_connecting_when_the_device_clock_is_not_ready():
    settings = config()
    settings["mqtt"]["tls"] = {
        "enabled": True,
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
        "server_hostname": "abc.emqxsl.com",
    }
    year = [2019]
    client = FakeClient()
    tracer = MqttTracer(
        settings,
        ConnectedWiFi(),
        client_factory=lambda **_kwargs: client,
        utc_year=lambda: year[0],
        sync_time=lambda: year.__setitem__(0, 2026),
    )

    tracer.poll()

    assert tracer.status() == {
        "enabled": True,
        "connected": True,
        "last_error": None,
    }


def test_tls_does_not_connect_until_the_device_clock_is_ready():
    settings = config()
    settings["mqtt"]["tls"] = {
        "enabled": True,
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
        "server_hostname": "abc.emqxsl.com",
    }
    tracer = MqttTracer(
        settings,
        ConnectedWiFi(),
        client_factory=lambda **_kwargs: pytest.fail("TLS client must not be created"),
        utc_year=lambda: 2019,
        sync_time=lambda: None,
    )

    tracer.poll()

    assert tracer.status() == {
        "enabled": True,
        "connected": False,
        "last_error": "MQTT_TLS_CLOCK_NOT_READY",
    }


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


def test_mqtt_job_fails_without_printer_delivery_when_ethernet_link_is_down():
    def link_down():
        raise RpcError("ETHERNET_LINK_DOWN", "W5500 physical link is down")

    service = FakeJobService()
    tracer, client = connected_tracer(
        service,
        JobLedger(max_completed_ids=2),
        before_delivery=link_down,
    )
    callback = client.callback
    assert callback is not None

    callback(
        b"v1/devices/paperbridge-dev-001/print-jobs",
        (FIXTURES / "valid-text-feed.json").read_bytes(),
    )

    assert service.calls == [(json.loads((FIXTURES / "valid-text-feed.json").read_text()), False)]
    assert client.published[-1][1] == {
        "schema_version": "1",
        "kind": "job_result",
        "job_id": "job-hello-001",
        "device_id": "paperbridge-dev-001",
        "status": "failed",
        "error_code": "ETHERNET_LINK_DOWN",
    }


def test_qos_redelivery_reports_duplicate_without_a_second_printer_delivery():
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
    assert client.published[-2][1]["status"] == "delivered_to_printer"
    assert client.published[-1][1] == {
        "schema_version": "1",
        "kind": "job_result",
        "job_id": "job-hello-001",
        "device_id": "paperbridge-dev-001",
        "status": "duplicate",
        "error_code": "DUPLICATE_JOB",
    }


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


class MemorySocket:
    def __init__(self, raw):
        self.raw = raw
        self.read_sizes = []
        self.writes = []
        self.closed = False

    def read(self, size):
        self.read_sizes.append(size)
        value, self.raw = self.raw[:size], self.raw[size:]
        return value

    def setblocking(self, _flag):
        pass

    def write(self, raw, size=None):
        if isinstance(raw, str):
            raw = raw.encode()
        self.writes.append(bytes(raw[:size]))
        return len(self.writes[-1])

    def close(self):
        self.closed = True


def mqtt_length(size):
    encoded = bytearray()
    while size > 127:
        encoded.append((size & 127) | 128)
        size >>= 7
    encoded.append(size)
    return bytes(encoded)


def publish_packet(topic, payload, retained=False, qos=1):
    body = len(topic).to_bytes(2, "big") + topic
    if qos:
        body += b"\x00\x01"
    body += payload
    return bytes([0x30 | (qos << 1) | retained]) + mqtt_length(len(body)) + body


def wire_client(tracer, raw):
    client = MqttTracer._default_client_factory(
        **tracer.settings, max_topic_bytes=len(tracer.print_jobs_topic)
    )
    client.set_callback(tracer._handle_message)
    client.sock = MemorySocket(raw)
    return client


def test_wire_retained_jobs_never_deliver_across_fresh_device_instances():
    transport = RecordingTransport()
    settings = config()
    service = JobService(settings, PrintCoordinator(EscPosRenderer(), transport))
    payload = (FIXTURES / "valid-text-feed.json").read_bytes()
    for _ in range(2):
        tracer, published = connected_tracer(service, settings=settings)
        client = wire_client(
            tracer, publish_packet(tracer.print_jobs_topic, payload, retained=True)
        )
        client.wait_msg()
        assert transport.payloads == []
        assert published.published == []
        assert tracer.last_error == "RETAINED_MQTT_MESSAGE"
        assert client.sock.writes == [b"\x40\x02\x00\x01"]
        # Rejection does not consume the job ID; a subsequent explicit live job works.
        client.sock.raw = publish_packet(tracer.print_jobs_topic, payload)
        client.wait_msg()
        assert transport.payloads == [b"\x1b@Hello from Paperbridge\n\n\n\n"]
        assert published.published[-1][1]["status"] == "delivered_to_printer"
        transport.payloads.clear()


@pytest.mark.parametrize("payload_size", [65_537, 1_048_576])
def test_wire_oversized_publish_is_rejected_before_payload_read(payload_size):
    tracer, _published = connected_tracer(FakeJobService())
    client = wire_client(tracer, publish_packet(tracer.print_jobs_topic, b"x" * payload_size))
    from src.mqtt_client import MQTTException

    with pytest.raises(MQTTException, match="MQTT_PACKET_TOO_LARGE|MQTT_PAYLOAD_TOO_LARGE"):
        client.wait_msg()
    assert max(client.sock.read_sizes) <= len(tracer.print_jobs_topic)
    assert client.sock.closed
    assert tracer.job_service.calls == []


@pytest.mark.parametrize(
    "raw",
    [
        b"\x32\x80\x80\x80\x80\x00",  # more than four remaining-length bytes
        b"\x32\x80\x00",  # noncanonical remaining-length encoding
        b"\x32\x01\x00",  # no room for a topic length
        b"\x32\x04\xff\xff",  # topic extends beyond the packet
        b"\x32\x04\x00\x01a\x00",  # truncated packet ID
    ],
)
def test_wire_malformed_length_is_rejected_without_delivery(raw):
    tracer, _published = connected_tracer(FakeJobService())
    client = wire_client(tracer, raw)
    from src.mqtt_client import MQTTException

    with pytest.raises(MQTTException, match="INVALID_MQTT_PACKET"):
        client.wait_msg()
    assert max(client.sock.read_sizes) <= 2
    assert client.sock.closed
    assert tracer.job_service.calls == []


def test_wire_maximum_payload_is_allowed_and_qos_one_is_acknowledged():
    tracer, _published = connected_tracer()
    payload = b"x" * tracer.settings["max_message_bytes"]
    client = wire_client(tracer, publish_packet(tracer.print_jobs_topic, payload))
    received = []
    client.set_callback(lambda *args: received.append(args))
    client.wait_msg()
    assert received == [(tracer.print_jobs_topic, payload, False)]
    assert not client.sock.closed
    assert client.sock.writes == [b"\x40\x02\x00\x01"]


def test_wire_subscribe_and_publish_qos_one_handshakes_are_preserved():
    tracer, _published = connected_tracer()
    client = wire_client(tracer, b"\x90\x03\x00\x01\x01")
    client.subscribe(tracer.print_jobs_topic, qos=1)
    assert client.sock.raw == b""
    assert client.sock.writes[0][0] == 0x82

    client.sock.raw = b"\x40\x02\x00\x02"
    client.publish(tracer.job_results_topic, b"{}", qos=1, retain=False)
    assert client.sock.raw == b""
    assert not client.sock.closed
    assert client.sock.writes[-1] == b"{}"


def test_wire_qos_zero_and_ping_response_remain_supported():
    tracer, _published = connected_tracer()
    client = wire_client(tracer, publish_packet(tracer.jobs_topic, b"{}", qos=0))
    received = []
    client.set_callback(lambda *args: received.append(args))
    client.wait_msg()
    assert received == [(tracer.jobs_topic, b"{}", False)]
    assert client.sock.writes == []
    client.sock.raw = b"\xd0\x00"
    assert client.wait_msg() is None
    assert not client.sock.closed


def test_wire_truncated_payload_never_reaches_callback():
    from src.mqtt_client import MQTTException

    tracer, _published = connected_tracer(FakeJobService())
    payload = (FIXTURES / "valid-text-feed.json").read_bytes()
    client = wire_client(tracer, publish_packet(tracer.print_jobs_topic, payload)[:-1])
    with pytest.raises(MQTTException, match="INVALID_MQTT_PACKET"):
        client.wait_msg()
    assert client.sock.closed
    assert tracer.job_service.calls == []


def test_wire_payload_limit_cannot_be_bypassed_with_a_shorter_topic():
    from src.mqtt_client import MQTTException

    tracer, _published = connected_tracer(FakeJobService())
    client = wire_client(tracer, publish_packet(b"a", b"x" * 65_537))
    with pytest.raises(MQTTException, match="MQTT_PAYLOAD_TOO_LARGE"):
        client.wait_msg()
    assert max(client.sock.read_sizes) == 2
    assert client.sock.closed
    assert tracer.job_service.calls == []


def test_wire_default_client_connects_with_clean_session_and_bounded_factory_settings(monkeypatch):
    from src import mqtt_client

    tracer, _published = connected_tracer()

    class HandshakeSocket(MemorySocket):
        def settimeout(self, timeout):
            self.timeout = timeout

        def connect(self, address):
            self.address = address

    sock = HandshakeSocket(b"\x20\x02\x00\x00")
    monkeypatch.setattr(
        mqtt_client,
        "socket",
        types.SimpleNamespace(
            socket=lambda: sock,
            getaddrinfo=lambda *_args: [(None, None, None, None, ("192.0.2.1", 1883))],
        ),
    )
    client = MqttTracer._default_client_factory(
        **tracer.settings, max_topic_bytes=len(tracer.print_jobs_topic)
    )
    assert client.connect() == 0
    assert sock.raw == b""
    assert sock.address == ("192.0.2.1", 1883)
    assert sock.writes[0][0] == 0x10
    assert sock.writes[1] == b"\x04MQTT\x04\xc2\x00\x1e"
    assert client.max_message_bytes == tracer.settings["max_message_bytes"]
    assert client.max_topic_bytes == len(tracer.print_jobs_topic)
