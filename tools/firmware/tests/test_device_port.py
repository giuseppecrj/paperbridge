import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "paperbridge_device_port", Path("tools/firmware/device_port.py")
)
assert SPEC is not None and SPEC.loader is not None
device_port = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(device_port)


def test_rejects_empty_and_numeric_ports():
    with pytest.raises(SystemExit, match="device path"):
        device_port.require_device_port("")
    with pytest.raises(SystemExit, match="not the VID/PID"):
        device_port.require_device_port("12346")


def test_rejects_missing_dev_path(tmp_path):
    missing = tmp_path / "cu.missing"
    with pytest.raises(SystemExit, match="does not exist"):
        device_port.require_device_port(f"/dev/{missing.name}-not-real")


def test_rejects_missing_non_dev_path(tmp_path):
    missing = tmp_path / "cu.usbmodem-not-real"
    with pytest.raises(SystemExit, match="does not exist"):
        device_port.require_device_port(str(missing))


def test_accepts_existing_dev_path(tmp_path, monkeypatch):
    port = tmp_path / "cu.usbmodem101"
    port.write_text("")
    monkeypatch.setattr(device_port.Path, "exists", lambda self: str(self) == str(port))
    assert device_port.require_device_port(str(port)) == str(port)
