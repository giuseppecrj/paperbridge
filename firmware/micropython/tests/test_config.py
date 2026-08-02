import copy
import json
from pathlib import Path

import pytest
from src.config import ConfigurationError, redacted, validate_config


def example():
    return json.loads(Path("firmware/micropython/config.example.json").read_text())


def test_example_configuration_is_valid():
    assert validate_config(example())["printer"]["port"] == 9100


def test_mqtt_password_is_redacted_from_configuration_output():
    config = example()

    assert validate_config(config)["mqtt"]["port"] == 1883
    assert redacted(config)["mqtt"]["password"] == "***"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("ethernet", "address"), "999.1.1.1"),
        (("printer", "port"), 0),
        (("serial", "max_line_bytes"), 1_000_000),
    ],
)
def test_invalid_configuration_is_rejected(path, value):
    config = copy.deepcopy(example())
    config[path[0]][path[1]] = value
    with pytest.raises(ConfigurationError):
        validate_config(config)
