import io
import json
from pathlib import Path

from src.app import build_app

app = __import__("src.app", None, None, ("_start_serial_server",))


def test_build_app_composes_one_mqtt_tracer_when_enabled(tmp_path):
    config = json.loads(Path("firmware/micropython/config.example.json").read_text())
    config["wifi"]["enabled"] = True
    config["mqtt"]["enabled"] = True
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    server, wifi, tracer = build_app(
        reader=io.StringIO(), writer=io.StringIO(), config_path=str(config_path)
    )

    assert server.max_line_bytes == 4096
    assert wifi is not None
    assert tracer is not None
    assert tracer.jobs_topic == b"v1/devices/paperbridge-dev-001/jobs"
    assert tracer.print_jobs_topic == b"v1/devices/paperbridge-dev-001/print-jobs"
    assert tracer.wifi is not None
    assert tracer.wifi.settings == config["wifi"]
    router = server.dispatch.__self__
    assert tracer.job_service is router.job_service


def test_build_app_composes_wifi_without_mqtt_when_only_wifi_is_enabled(tmp_path):
    config = json.loads(Path("firmware/micropython/config.example.json").read_text())
    config["wifi"]["enabled"] = True
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

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
