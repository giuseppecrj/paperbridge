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
    assert config["mqtt"]["max_message_bytes"] == 65_536


def test_legacy_mqtt_message_bound_remains_boot_compatible():
    config = example()
    config["mqtt"]["max_message_bytes"] = 1024

    assert validate_config(config)["mqtt"]["max_message_bytes"] == 1024


def test_network_passwords_are_redacted_from_configuration_output():
    config = example()

    assert validate_config(config)["mqtt"]["port"] == 1883
    assert redacted(config)["mqtt"]["password"] == "***"
    assert redacted(config)["wifi"]["password"] == "***"


def test_device_config_avoids_unavailable_micropython_string_methods():
    source = Path("firmware/micropython/src/config.py").read_text()

    assert ".isalnum(" not in source


def test_tls_requires_a_pem_ca_and_sni_and_redacts_the_ca():
    config = example()
    config["mqtt"]["tls"] = {
        "enabled": True,
        "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----\n",
        "server_hostname": "abc.emqxsl.com",
    }

    validated = validate_config(config)

    assert validated["mqtt"]["tls"]["server_hostname"] == "abc.emqxsl.com"
    assert redacted(validated)["mqtt"]["tls"]["ca_certificate"] == "***"


@pytest.mark.parametrize(
    "tls",
    [
        {"enabled": True},
        {
            "enabled": True,
            "ca_certificate": "not a certificate",
            "server_hostname": "abc.emqxsl.com",
        },
        {
            "enabled": True,
            "ca_certificate": "-----BEGIN CERTIFICATE-----\nCA\n-----END CERTIFICATE-----",
            "server_hostname": "192.0.2.1",
        },
    ],
)
def test_tls_configuration_rejects_incomplete_or_unsafe_trust_settings(tls):
    config = example()
    config["mqtt"]["tls"] = tls

    with pytest.raises(ConfigurationError):
        validate_config(config)


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
        (("wifi", "dns"), "not-an-ip-address"),
        (("mqtt", "allow_cut"), 1),
        (("mqtt", "max_message_bytes"), 65_537),
    ],
)
def test_invalid_configuration_is_rejected(path, value):
    config = copy.deepcopy(example())
    config[path[0]][path[1]] = value
    with pytest.raises(ConfigurationError):
        validate_config(config)
