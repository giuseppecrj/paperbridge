import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "paperbridge_deploy", Path("tools/firmware/deploy.py")
)
assert SPEC is not None and SPEC.loader is not None
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def test_firmware_root_is_repo_absolute_not_cwd():
    root = deploy.firmware_root()
    assert root.is_absolute()
    assert root.name == "micropython"
    assert (root / "main.py").exists()
    assert root == Path(__file__).resolve().parents[3] / "firmware" / "micropython"


def test_wait_for_ready_retries_until_probe_succeeds():
    attempts = {"n": 0}
    sleeps = []

    def path_exists(_port):
        return True

    def probe(_port):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise SystemExit("not ready")

    deploy.wait_for_ready(
        "/dev/cu.usbmodem101",
        timeout_s=2.0,
        interval_s=0.01,
        sleep=lambda s: sleeps.append(s),
        path_exists=path_exists,
        probe=probe,
    )
    assert attempts["n"] == 3
    assert sleeps


def test_wait_for_ready_times_out(monkeypatch):
    with pytest.raises(SystemExit, match="not ready"):
        deploy.wait_for_ready(
            "/dev/cu.usbmodem101",
            timeout_s=0.05,
            interval_s=0.01,
            sleep=lambda _s: None,
            path_exists=lambda _p: False,
            probe=lambda _p: None,
        )


def test_default_probe_is_application_ping_not_ensure_micropython(monkeypatch):
    # Default probe is application_ping (system.ping); ensure_micropython stays pre-deploy only.
    seen = {}

    def capture(port):
        seen["port"] = port

    monkeypatch.setattr(deploy, "application_ping", capture)
    deploy.wait_for_ready(
        "/dev/cu.usbmodem101",
        timeout_s=1.0,
        interval_s=0.01,
        sleep=lambda _s: None,
        path_exists=lambda _p: True,
    )
    assert seen["port"] == "/dev/cu.usbmodem101"
    assert deploy.wait_for_ready.__kwdefaults__["probe"] is None


def test_application_ping_requires_ok_status():
    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def request(self, command, params=None):
            assert command == "system.ping"
            return {"status": "busy"}

    with pytest.raises(SystemExit, match="application RPC not ready"):
        deploy.application_ping("/dev/cu.usbmodem101", client_factory=FakeClient)


def test_application_ping_ok():
    class FakeClient:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def request(self, command, params=None):
            return {"status": "ok"}

    deploy.application_ping("/dev/cu.usbmodem101", client_factory=FakeClient)


def test_source_files_are_individual_py_under_src():
    files = deploy.source_files()
    assert files
    assert deploy.firmware_root() / "src" / "mqtt_client.py" in files
    assert all(path.suffix == ".py" for path in files)
    assert all(path.parent.name == "src" for path in files)
