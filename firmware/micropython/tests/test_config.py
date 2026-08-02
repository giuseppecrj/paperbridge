import copy
import json
from pathlib import Path

import pytest
from src.config import ConfigurationError, redacted, validate_config


def example():
    return json.loads(Path("firmware/micropython/config.example.json").read_text())


def test_example_configuration_is_valid():
    config = validate_config(example())
    assert config["printer"]["port"] == 9100
    assert config["mqtt"]["allow_cut"] is False


def test_network_passwords_are_redacted_from_configuration_output():
    config = example()

    assert validate_config(config)["mqtt"]["port"] == 1883
    assert redacted(config)["mqtt"]["password"] == "***"
    assert redacted(config)["wifi"]["password"] == "***"


def test_device_id_must_be_a_safe_mqtt_topic_segment():
    config = example()
    config["device_id"] = "device/other"

    with pytest.raises(ConfigurationError, match="safe MQTT topic segment"):
        validate_config(config)


def test_enabled_mqtt_requires_enabled_wifi():
    config = example()
    config["mqtt"]["enabled"] = True

    with pytest.raises(ConfigurationError, match="mqtt requires wifi.enabled=true"):
        validate_config(config)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("ethernet", "address"), "999.1.1.1"),
        (("printer", "port"), 0),
        (("serial", "max_line_bytes"), 1_000_000),
        (("wifi", "ssid"), ""),
        (("mqtt", "allow_cut"), 1),
        (("mqtt", "max_message_bytes"), 2048),
    ],
)
def test_invalid_configuration_is_rejected(path, value):
    config = copy.deepcopy(example())
    config[path[0]][path[1]] = value
    with pytest.raises(ConfigurationError):
        validate_config(config)
