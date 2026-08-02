import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "paperbridge_flash", Path("tools/firmware/flash_micropython.py")
)
assert SPEC is not None and SPEC.loader is not None
flash = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(flash)


def test_sha256_mismatch_aborts_before_esptool(tmp_path, monkeypatch):
    firmware = tmp_path / "fw.bin"
    firmware.write_bytes(b"not-the-image")
    called = []

    monkeypatch.setattr(
        flash.subprocess,
        "run",
        lambda *args, **kwargs: called.append(args) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        flash,
        "require_device_port",
        lambda port: port,
    )

    with pytest.raises(SystemExit, match="SHA-256 mismatch"):
        flash.main(
            [
                "--port",
                "/dev/cu.usbmodem101",
                "--firmware",
                str(firmware),
                "--sha256",
                "0" * 64,
            ]
        )
    assert called == []


def test_matching_sha256_invokes_esptool(tmp_path, monkeypatch):
    firmware = tmp_path / "fw.bin"
    payload = b"official-image"
    firmware.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    called = []

    monkeypatch.setattr(
        flash.subprocess,
        "run",
        lambda cmd, check=False, **kwargs: called.append(cmd) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(flash, "require_device_port", lambda port: port)

    flash.main(
        [
            "--port",
            "/dev/cu.usbmodem101",
            "--firmware",
            str(firmware),
            "--sha256",
            digest,
        ]
    )
    assert called
    assert "--port" in called[0]
    assert str(firmware) in called[0]


def test_sha256_is_required(monkeypatch):
    monkeypatch.setattr(flash, "require_device_port", lambda port: port)
    with pytest.raises(SystemExit):
        flash.main(["--port", "/dev/cu.usbmodem101", "--firmware", "x.bin"])
