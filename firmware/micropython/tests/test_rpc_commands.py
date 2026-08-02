import json
from pathlib import Path

import pytest
from src.escpos import EscPosRenderer
from src.print_coordinator import PrintCoordinator
from src.rpc_commands import CommandRouter
from src.serial_rpc import RpcError

FIXTURES = Path("packages/protocol/fixtures/print-job-v1")


def load(name):
    return json.loads((FIXTURES / name).read_text())


class FakeEthernet:
    def __init__(self):
        self.reconnect_calls = 0

    def initialize(self):
        return {"initialized": True}

    def reconnect(self):
        self.reconnect_calls += 1
        return {"initialized": True, "link_up": True}

    def status(self):
        return {"link_up": True, "raw_status": 1}

    def configure_static(self):
        return {"ifconfig": ["192.168.1.50"]}


class FakeTransport:
    def __init__(self):
        self.payloads = []

    def endpoint(self):
        return "192.168.1.87:9100"

    def probe(self):
        return {"reachable": True}

    def send(self, payload):
        self.payloads.append(payload)
        return {
            "status": "delivered_to_printer",
            "bytes_sent": len(payload),
            "printer_endpoint": self.endpoint(),
        }


class FakeMqtt:
    def status(self):
        return {"connected": False, "last_error": "MQTT_CONNECT_FAILED: connection refused"}


class FakeWiFi:
    def __init__(self):
        self.calls = []

    def status(self):
        return {
            "connected": True,
            "ifconfig": ("192.168.1.50", "255.255.255.0", "192.168.1.1", "192.168.1.1"),
        }

    def disconnect(self):
        self.calls.append("disconnect")
        return {"suspended": True}

    def reconnect(self):
        self.calls.append("reconnect")
        return {"suspended": False}


class FakeCoordinator:
    def print_test(self, text):
        return {"text": text}

    def feed_test(self):
        return {"feed": True}

    def cut_test(self):
        return {"cut": True}


def config():
    return {
        "device_id": "test",
        "environment": "test",
        "serial": {"max_line_bytes": 4096},
        "ethernet": {},
        "printer": {},
        "queue": {},
    }


def router():
    return CommandRouter(config(), FakeEthernet(), FakeCoordinator(), FakeTransport())


def print_job_router(transport):
    settings = config()
    settings["device_id"] = "paperbridge-dev-001"
    return CommandRouter(
        settings,
        FakeEthernet(),
        PrintCoordinator(EscPosRenderer(), transport),
        transport,
    )


def test_ping_and_info():
    instance = router()
    assert instance.dispatch("system.ping", {}) == {"status": "ok"}
    assert instance.dispatch("system.info", {})["device_id"] == "test"


def test_ethernet_reconnect_requires_explicit_boolean_confirmation():
    instance = router()

    with pytest.raises(RpcError) as error:
        instance.dispatch("ethernet.reconnect", {"confirm": 1})

    assert error.value.code == "INVALID_RPC_REQUEST"
    assert instance.dispatch("ethernet.reconnect", {"confirm": True}) == {
        "initialized": True,
        "link_up": True,
    }
    assert instance.ethernet.reconnect_calls == 1


def test_cut_requires_explicit_boolean_confirmation():
    with pytest.raises(RpcError) as error:
        router().dispatch("printer.cut_test", {"confirm": 1})
    assert error.value.code == "INVALID_RPC_REQUEST"
    assert router().dispatch("printer.cut_test", {"confirm": True}) == {"cut": True}


def test_printer_probe_uses_tcp_reachability_when_lan_status_is_stale():
    instance = router()
    instance.ethernet.status = lambda: {"link_up": False, "raw_status": 1}

    assert instance.dispatch("printer.probe", {}) == {"reachable": True}


@pytest.mark.parametrize(
    ("command", "params"),
    [
        ("printer.print_test", {"text": "test"}),
        ("printer.feed_test", {}),
        ("printer.cut_test", {"confirm": True}),
    ],
)
def test_printer_output_commands_still_require_physical_link(command, params):
    instance = router()
    instance.ethernet.status = lambda: {"link_up": False, "raw_status": 1}

    with pytest.raises(RpcError) as error:
        instance.dispatch(command, params)

    assert error.value.code == "ETHERNET_LINK_DOWN"


def test_print_job_still_requires_physical_link():
    transport = FakeTransport()
    instance = print_job_router(transport)
    instance.ethernet.status = lambda: {"link_up": False, "raw_status": 1}

    with pytest.raises(RpcError) as error:
        instance.dispatch("job.submit", {"job": load("valid-text-feed.json")})

    assert error.value.code == "ETHERNET_LINK_DOWN"
    assert transport.payloads == []


def test_wifi_status_exposes_control_plane_without_printer_access():
    instance = CommandRouter(
        config(), FakeEthernet(), FakeCoordinator(), FakeTransport(), wifi=FakeWiFi()
    )

    assert instance.dispatch("wifi.status", {}) == {
        "connected": True,
        "ifconfig": ("192.168.1.50", "255.255.255.0", "192.168.1.1", "192.168.1.1"),
    }


def test_wifi_control_requires_explicit_confirmation_without_printer_access():
    wifi = FakeWiFi()
    instance = CommandRouter(
        config(), FakeEthernet(), FakeCoordinator(), FakeTransport(), wifi=wifi
    )

    for params in ({}, {"confirm": False}, {"confirm": 1}):
        with pytest.raises(RpcError) as error:
            instance.dispatch("wifi.disconnect", params)
        assert error.value.code == "INVALID_RPC_REQUEST"
    assert instance.dispatch("wifi.disconnect", {"confirm": True}) == {"suspended": True}
    assert instance.dispatch("wifi.reconnect", {"confirm": True}) == {"suspended": False}
    assert wifi.calls == ["disconnect", "reconnect"]


def test_wifi_control_rejects_an_unconfigured_adapter():
    with pytest.raises(RpcError) as error:
        router().dispatch("wifi.disconnect", {"confirm": True})
    assert error.value.code == "WIFI_DISABLED"


def test_mqtt_status_exposes_tracer_connectivity_without_printer_access():
    instance = CommandRouter(
        config(), FakeEthernet(), FakeCoordinator(), FakeTransport(), mqtt=FakeMqtt()
    )

    assert instance.dispatch("mqtt.status", {}) == {
        "connected": False,
        "last_error": "MQTT_CONNECT_FAILED: connection refused",
    }


def test_unsupported_command_is_stable():
    with pytest.raises(RpcError) as error:
        router().dispatch("cloud.start", {})
    assert error.value.code == "UNSUPPORTED_RPC_COMMAND"


def test_unused_bringup_aliases_are_not_wired():
    for command in ("config.reload", "queue.status", "printer.send_fixture"):
        with pytest.raises(RpcError) as error:
            router().dispatch(command, {})
        assert error.value.code == "UNSUPPORTED_RPC_COMMAND"


def test_submit_job_routes_fixture_to_shared_renderer_and_transport():
    transport = FakeTransport()
    instance = print_job_router(transport)

    result = instance.dispatch("job.submit", {"job": load("valid-text-feed.json")})

    assert result == {
        "status": "delivered_to_printer",
        "bytes_sent": 28,
        "printer_endpoint": "192.168.1.87:9100",
        "job_id": "job-hello-001",
    }
    assert transport.payloads == [b"\x1b@Hello from Paperbridge\n\n\n\n"]


@pytest.mark.parametrize(
    ("job", "params", "code"),
    [
        (load("invalid-control-text.json"), {}, "INVALID_PRINT_JOB"),
        (load("valid-cut.json"), {}, "UNAUTHORIZED_CUT"),
        (load("valid-text-feed.json"), {"allow_cut": 1}, "INVALID_RPC_REQUEST"),
        ({**load("valid-text-feed.json"), "schema_version": "2"}, {}, "INVALID_PRINT_JOB"),
        ({**load("valid-text-feed.json"), "device_id": "other-device"}, {}, "WRONG_DEVICE"),
        (
            {
                **load("valid-text-feed.json"),
                "content": {
                    "kind": "receipt",
                    "blocks": [{"type": "text", "text": "x" * 2048}] * 100,
                },
            },
            {},
            "JOB_TOO_LARGE",
        ),
    ],
)
def test_submit_job_rejects_before_printer_delivery(job, params, code):
    transport = FakeTransport()
    instance = print_job_router(transport)

    with pytest.raises(RpcError) as error:
        instance.dispatch("job.submit", {"job": job, **params})

    assert error.value.code == code
    assert transport.payloads == []


def test_submit_job_allows_an_explicitly_authorized_cut():
    transport = FakeTransport()
    instance = print_job_router(transport)

    assert (
        instance.dispatch("job.submit", {"job": load("valid-cut.json"), "allow_cut": True})[
            "job_id"
        ]
        == "job-cut-001"
    )
    assert transport.payloads == [b"\x1b@Cut me\n\x1dV\x01"]
