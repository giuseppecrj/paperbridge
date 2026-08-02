import pytest
from src.rpc_commands import CommandRouter
from src.serial_rpc import RpcError


class FakeEthernet:
    def initialize(self):
        return {"initialized": True}

    def status(self):
        return {"link_up": True, "raw_status": 1}

    def configure_static(self):
        return {"ifconfig": ["192.168.1.50"]}


class FakeTransport:
    def endpoint(self):
        return "192.168.1.87:9100"

    def probe(self):
        return {"reachable": True}


class FakeCoordinator:
    def print_test(self, text):
        return {"text": text}

    def feed_test(self):
        return {"feed": True}

    def cut_test(self):
        return {"cut": True}


def router():
    config = {
        "device_id": "test",
        "environment": "test",
        "serial": {"max_line_bytes": 4096},
        "ethernet": {},
        "printer": {},
        "queue": {},
    }
    return CommandRouter(config, FakeEthernet(), FakeCoordinator(), FakeTransport())


def test_ping_and_info():
    instance = router()
    assert instance.dispatch("system.ping", {}) == {"status": "ok"}
    assert instance.dispatch("system.info", {})["device_id"] == "test"


def test_cut_requires_explicit_boolean_confirmation():
    with pytest.raises(RpcError) as error:
        router().dispatch("printer.cut_test", {"confirm": 1})
    assert error.value.code == "INVALID_RPC_REQUEST"
    assert router().dispatch("printer.cut_test", {"confirm": True}) == {"cut": True}


def test_printer_commands_require_physical_link():
    instance = router()
    instance.ethernet.status = lambda: {"link_up": False}
    with pytest.raises(RpcError) as error:
        instance.dispatch("printer.probe", {})
    assert error.value.code == "ETHERNET_LINK_DOWN"


def test_unsupported_command_is_stable():
    with pytest.raises(RpcError) as error:
        router().dispatch("cloud.start", {})
    assert error.value.code == "UNSUPPORTED_RPC_COMMAND"


def test_unused_bringup_aliases_are_not_wired():
    for command in ("config.reload", "queue.status", "printer.send_fixture"):
        with pytest.raises(RpcError) as error:
            router().dispatch(command, {})
        assert error.value.code == "UNSUPPORTED_RPC_COMMAND"
