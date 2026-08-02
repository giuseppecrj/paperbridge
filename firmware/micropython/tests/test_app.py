import io
import json
from pathlib import Path

from src.app import build_app


def test_build_app_composes_one_mqtt_tracer_when_enabled(tmp_path):
    config = json.loads(Path("firmware/micropython/config.example.json").read_text())
    config["mqtt"]["enabled"] = True
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))

    server, tracer = build_app(
        reader=io.StringIO(), writer=io.StringIO(), config_path=str(config_path)
    )

    assert server.max_line_bytes == 4096
    assert tracer is not None
    assert tracer.jobs_topic == b"v1/devices/paperbridge-dev-001/jobs"
