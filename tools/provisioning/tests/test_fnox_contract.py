from pathlib import Path

import tomllib

FNOX_TEXT = Path("fnox.toml").read_text()
FNOX = tomllib.loads(FNOX_TEXT)
JUSTFILE = Path("justfile").read_text()
ENV_EXAMPLE = Path(".env.example").read_text()


def recipe(name):
    return JUSTFILE.split(f"\n{name}:\n", 1)[1].split("\n\n", 1)[0]


def test_fnox_uses_local_defaults_with_device_and_production_overlays():
    assert FNOX["providers"] == {"onepass": {"type": "1password"}}
    assert set(FNOX["secrets"]) == {"PAPERBRIDGE_MQTT_PASSWORD"}
    assert set(FNOX["profiles"]) == {"device", "production"}
    assert set(FNOX["profiles"]["device"]["secrets"]) == {"PAPERBRIDGE_WIFI_PASSWORD"}
    assert set(FNOX["profiles"]["production"]["secrets"]) == {"PAPERBRIDGE_MQTT_PASSWORD"}
    assert (
        FNOX["secrets"]["PAPERBRIDGE_MQTT_PASSWORD"]["value"]
        != FNOX["profiles"]["production"]["secrets"]["PAPERBRIDGE_MQTT_PASSWORD"]["value"]
    )


def test_fnox_has_no_service_account_or_non_secret_wifi_mapping():
    assert "OP_SERVICE_ACCOUNT_TOKEN" not in FNOX_TEXT
    assert "PAPERBRIDGE_WIFI_SSID" not in FNOX_TEXT
    assert "keychain" not in FNOX["providers"]


def test_fnox_recipes_use_default_inheritance_and_bounded_overlays():
    assert "--no-defaults" not in JUSTFILE
    assert "-P host" not in JUSTFILE
    assert "fnox profiles" in recipe("lint")

    for name in ("secrets-check", "configure-device"):
        assert "-P device" in recipe(name)

    for name in ("production-secrets-check", "production-configure"):
        assert "-P production" in recipe(name)

    for name in ("test-hardware-network-recovery", "mqtt-probe", "api"):
        assert " -P " not in recipe(name)


def test_live_secret_checks_do_not_print_values():
    local_check = recipe("secrets-check")
    assert "PAPERBRIDGE_MQTT_PASSWORD" in local_check
    assert "PAPERBRIDGE_WIFI_SSID" in local_check
    assert "PAPERBRIDGE_WIFI_PASSWORD" in local_check
    assert "print(" not in local_check

    production_check = recipe("production-secrets-check")
    assert "PAPERBRIDGE_MQTT_PASSWORD" in production_check
    assert "print(" not in production_check


def test_local_environment_owns_wifi_name_not_runtime_password_file():
    assert "PAPERBRIDGE_WIFI_SSID=" in ENV_EXAMPLE
    assert "PAPERBRIDGE_MQTT_PASSWORD_FILE" not in ENV_EXAMPLE
