import pytest
from paperbridge_cli import ports
from paperbridge_cli.ports import PortSelectionError


def test_explicit_and_environment_ports_win():
    assert ports.resolve_port("/dev/explicit", {"PAPERBRIDGE_PORT": "/dev/env"}) == "/dev/explicit"
    assert ports.resolve_port(None, {"PAPERBRIDGE_PORT": "/dev/env"}) == "/dev/env"


def test_filters_non_usb_pseudo_ports(monkeypatch):
    class Port:
        def __init__(self, device, vid=None):
            self.device = device
            self.description = "test"
            self.vid = vid
            self.pid = None

    monkeypatch.setattr(
        ports.list_ports,
        "comports",
        lambda: [
            Port("/dev/cu.Bluetooth-Incoming-Port"),
            Port("/dev/cu.debug-console"),
            Port("/dev/cu.usbmodem101", 12346),
        ],
    )
    monkeypatch.setattr(ports.glob, "glob", lambda _pattern: [])
    assert [item["device"] for item in ports.likely_ports()] == ["/dev/cu.usbmodem101"]


def test_does_not_choose_ambiguously(monkeypatch):
    monkeypatch.setattr(
        ports,
        "likely_ports",
        lambda: [{"device": "/dev/a"}, {"device": "/dev/b"}],
    )
    with pytest.raises(PortSelectionError, match="Multiple"):
        ports.resolve_port(None, {})
