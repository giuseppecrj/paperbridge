import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

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
    assert payload["wifi"]["enabled"] is False
    assert payload["mqtt"]["enabled"] is False
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert os.getcwd() == str(tmp_path)


def test_generate_networked_device_config_from_environment(tmp_path, monkeypatch):
    monkeypatch.delenv("PAPERBRIDGE_MQTT_ALLOW_CUT", raising=False)
    values = {
        "PAPERBRIDGE_DEVICE_ID": "paperbridge-dev-001",
        "PAPERBRIDGE_PRINTER_HOST": "192.168.4.87",
        "PAPERBRIDGE_WIFI_SSID": "Paperbridge Test Wi-Fi",
        "PAPERBRIDGE_WIFI_PASSWORD": "wifi-password",
        "PAPERBRIDGE_MQTT_HOST": "192.168.1.20",
        "PAPERBRIDGE_MQTT_USERNAME": "paperbridge-dev-001",
        "PAPERBRIDGE_MQTT_PASSWORD": "mqtt-password",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    output = tmp_path / "config.json"

    gen.main(["--from-env", "--output", str(output)])

    payload = json.loads(output.read_text())
    assert payload["device_id"] == "paperbridge-dev-001"
    assert payload["printer"]["host"] == "192.168.4.87"
    assert payload["wifi"] == {
        "enabled": True,
        "ssid": "Paperbridge Test Wi-Fi",
        "password": "wifi-password",
        "retry_interval_ms": 5000,
    }
    assert payload["mqtt"]["enabled"] is True
    assert payload["mqtt"]["host"] == "192.168.1.20"
    assert payload["mqtt"]["username"] == "paperbridge-dev-001"
    assert payload["mqtt"]["password"] == "mqtt-password"
    assert payload["mqtt"]["client_id"] == "paperbridge-dev-001"
    assert payload["mqtt"]["allow_cut"] is False
    assert stat.S_IMODE(output.stat().st_mode) == 0o600


def test_remote_cut_policy_requires_an_explicit_boolean(monkeypatch):
    monkeypatch.delenv("PAPERBRIDGE_MQTT_ALLOW_CUT", raising=False)
    assert gen.boolean_env("PAPERBRIDGE_MQTT_ALLOW_CUT", False) is False

    monkeypatch.setenv("PAPERBRIDGE_MQTT_ALLOW_CUT", "true")
    assert gen.boolean_env("PAPERBRIDGE_MQTT_ALLOW_CUT", False) is True

    monkeypatch.setenv("PAPERBRIDGE_MQTT_ALLOW_CUT", "1")
    with pytest.raises(SystemExit, match="must be true or false"):
        gen.boolean_env("PAPERBRIDGE_MQTT_ALLOW_CUT", False)


def test_generate_from_environment_fails_without_printing_secret_values(tmp_path, monkeypatch):
    for name in (
        "PAPERBRIDGE_PRINTER_HOST",
        "PAPERBRIDGE_WIFI_SSID",
        "PAPERBRIDGE_MQTT_HOST",
        "PAPERBRIDGE_MQTT_USERNAME",
        "PAPERBRIDGE_MQTT_PASSWORD",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PAPERBRIDGE_DEVICE_ID", "paperbridge-dev-001")
    monkeypatch.setenv("PAPERBRIDGE_WIFI_PASSWORD", "do-not-print-this")

    with pytest.raises(SystemExit, match="PAPERBRIDGE_PRINTER_HOST is required") as error:
        gen.main(["--from-env", "--output", str(tmp_path / "config.json")])

    assert "do-not-print-this" not in str(error.value)
