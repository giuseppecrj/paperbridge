import io
import json
from pathlib import Path

from src.app import build_app
from src.ethernet import EthernetError

app = __import__("src.app", None, None, ("_start_serial_server",))


def boot_ethernet(monkeypatch):
    class FakeEthernet:
        def __init__(self, _config):
            self.calls = []

        def initialize(self):
            self.calls.append("initialize")

        def configure_static(self):
            self.calls.append("configure_static")

    ethernet = FakeEthernet(None)
    monkeypatch.setattr(app, "W5500LAN", lambda _config: ethernet)
    return ethernet


def test_build_app_keeps_serial_rpc_available_when_ethernet_boot_fails(tmp_path, monkeypatch):
    class FailingEthernet:
        def __init__(self, _config):
            self.calls = []
            self.last_error = None

        def initialize(self):
            self.calls.append("initialize")
            raise EthernetError("W5500 initialization failed: SPI unavailable")

        def configure_static(self):
            raise AssertionError("Static configuration must not follow failed initialization")

    config = json.loads(Path("firmware/micropython/config.example.json").read_text())
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    ethernet = FailingEthernet(None)
    monkeypatch.setattr(app, "W5500LAN", lambda _config: ethernet)

    server, wifi, mqtt = build_app(
        reader=io.StringIO(), writer=io.StringIO(), config_path=str(config_path)
    )

    assert server.max_line_bytes == 65_536
    assert wifi is None
    assert mqtt is None
    assert ethernet.calls == ["initialize"]
    assert ethernet.last_error == "W5500 initialization failed: SPI unavailable"


def test_build_app_composes_one_mqtt_tracer_when_enabled(tmp_path, monkeypatch):
    config = json.loads(Path("firmware/micropython/config.example.json").read_text())
    config["wifi"]["enabled"] = True
    config["mqtt"]["enabled"] = True
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    ethernet = boot_ethernet(monkeypatch)

    server, wifi, tracer = build_app(
        reader=io.StringIO(), writer=io.StringIO(), config_path=str(config_path)
    )

    assert server.max_line_bytes == 65_536
    assert wifi is not None
    assert tracer is not None
    assert tracer.jobs_topic == b"v1/devices/paperbridge-dev-001/jobs"
    assert tracer.print_jobs_topic == b"v1/devices/paperbridge-dev-001/print-jobs"
    assert tracer.wifi is not None
    assert tracer.wifi.settings == config["wifi"]
    router = server.dispatch.__self__
    assert tracer.job_service is router.job_service
    assert tracer.before_delivery == router.require_ethernet_link
    assert ethernet.calls == ["initialize", "configure_static"]


def test_build_app_composes_wifi_without_mqtt_when_only_wifi_is_enabled(tmp_path, monkeypatch):
    config = json.loads(Path("firmware/micropython/config.example.json").read_text())
    config["wifi"]["enabled"] = True
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    boot_ethernet(monkeypatch)
    _server, wifi, mqtt = build_app(
        reader=io.StringIO(), writer=io.StringIO(), config_path=str(config_path)
    )

    assert wifi is not None
    assert mqtt is None


def test_serial_server_uses_a_background_thread_when_networking_is_enabled():
    class FakeThread:
        def __init__(self):
            self.target = None
            self.args = None

        def start_new_thread(self, target, args):
            self.target = target
            self.args = args

    class FakeServer:
        def run_forever(self):
            pass

    server = FakeServer()
    thread = FakeThread()

    app._start_serial_server(server, thread_module=thread)
    assert thread.target == server.run_forever
    assert thread.args == ()
