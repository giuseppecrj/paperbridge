import io
import json
from pathlib import Path

from src.app import build_app

app = __import__("src.app", None, None, ("_start_network_poller",))


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


class FakeMqtt:
    def __init__(self):
        self.last_error = None

    def record_error(self, message):
        self.last_error = message


def test_network_poller_uses_a_background_thread_without_replacing_serial_loop():
    class FakeThread:
        def __init__(self):
            self.target = None
            self.args = None

        def start_new_thread(self, target, args):
            self.target = target
            self.args = args

    mqtt = FakeMqtt()
    thread = FakeThread()

    assert app._start_network_poller(mqtt, thread_module=thread) is True
    assert thread.args is not None
    assert thread.args[0] is mqtt


def test_network_thread_start_failure_remains_observable_over_serial():
    class FailingThread:
        def start_new_thread(self, _target, _args):
            raise RuntimeError("threads unavailable")

    mqtt = FakeMqtt()

    assert app._start_network_poller(mqtt, thread_module=FailingThread()) is False
    assert mqtt.last_error == "NETWORK_THREAD_START_FAILED: threads unavailable"
