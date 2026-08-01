import json


class ConfigurationError(ValueError):
    pass


def _ipv4(value, field, nullable=False):
    if value is None and nullable:
        return
    if not isinstance(value, str):
        raise ConfigurationError(f"{field} must be an IPv4 string")
    parts = value.split(".")
    if len(parts) != 4:
        raise ConfigurationError(f"{field} must be an IPv4 address")
    try:
        valid = all(str(int(part)) == part and 0 <= int(part) <= 255 for part in parts)
    except ValueError:
        valid = False
    if not valid:
        raise ConfigurationError(f"{field} must be an IPv4 address")


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigurationError("configuration must be an object")
    for key in ("device_id", "environment", "serial", "ethernet", "printer", "queue"):
        if key not in config:
            raise ConfigurationError(f"missing configuration field: {key}")
    if not isinstance(config["device_id"], str) or not 1 <= len(config["device_id"]) <= 64:
        raise ConfigurationError("device_id must be 1..64 characters")

    max_line = config["serial"].get("max_line_bytes")
    if not isinstance(max_line, int) or not 256 <= max_line <= 16384:
        raise ConfigurationError("serial.max_line_bytes must be 256..16384")

    ethernet = config["ethernet"]
    _ipv4(ethernet.get("address"), "ethernet.address")
    _ipv4(ethernet.get("netmask"), "ethernet.netmask")
    _ipv4(ethernet.get("gateway"), "ethernet.gateway", nullable=True)
    _ipv4(ethernet.get("dns"), "ethernet.dns", nullable=True)

    printer = config["printer"]
    _ipv4(printer.get("host"), "printer.host")
    if not isinstance(printer.get("port"), int) or not 1 <= printer["port"] <= 65535:
        raise ConfigurationError("printer.port must be 1..65535")
    for field in ("connect_timeout_ms", "write_timeout_ms"):
        value = printer.get(field)
        if not isinstance(value, int) or not 100 <= value <= 60000:
            raise ConfigurationError(f"printer.{field} must be 100..60000")

    queue = config["queue"]
    for field in ("max_pending", "max_completed_ids"):
        value = queue.get(field)
        if not isinstance(value, int) or not 1 <= value <= 1000:
            raise ConfigurationError(f"queue.{field} must be 1..1000")
    return config


def load_config(path="config.json"):
    try:
        with open(path) as config_file:
            return validate_config(json.load(config_file))
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"unable to load configuration: {exc}") from exc


def redacted(config):
    # No secrets exist yet; return a JSON-safe copy so future redaction has one seam.
    try:
        return json.loads(json.dumps(config))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("configuration is not JSON-compatible") from exc
