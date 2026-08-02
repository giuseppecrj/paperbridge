import importlib.util
import json
import os
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "paperbridge_generate_device_config",
    Path("tools/provisioning/generate_device_config.py"),
)
assert SPEC is not None and SPEC.loader is not None
gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen)


def test_generate_from_non_repo_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "out" / "config.json"
    gen.main(
        [
            "--device-id",
            "paperbridge-dev-001",
            "--printer-host",
            "192.0.2.10",
            "--printer-port",
            "9100",
            "--output",
            str(output),
        ]
    )
    payload = json.loads(output.read_text())
    assert payload["device_id"] == "paperbridge-dev-001"
    assert payload["printer"]["host"] == "192.0.2.10"
    assert payload["printer"]["port"] == 9100
    assert os.getcwd() == str(tmp_path)
