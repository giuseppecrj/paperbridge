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


def _hostname(value, field):
    if not isinstance(value, str) or not 1 <= len(value) <= 253:
        raise ConfigurationError(f"{field} must be a DNS hostname")
    try:
        value.encode("ascii")
    except UnicodeError as exc:
        raise ConfigurationError(f"{field} must be a DNS hostname") from exc
    labels = value.split(".")
    hostname_characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
    if any(
        not 1 <= len(label) <= 63
        or label[0] == "-"
        or label[-1] == "-"
        or not all(character in hostname_characters for character in label)
        for label in labels
    ):
        raise ConfigurationError(f"{field} must be a DNS hostname")
    try:
        _ipv4(value, field)
    except ConfigurationError:
        return
    raise ConfigurationError(f"{field} must be a DNS hostname")


def _tls_settings(mqtt):
    tls = mqtt.setdefault("tls", {"enabled": False})
    if not isinstance(tls, dict) or not isinstance(tls.get("enabled"), bool):
        raise ConfigurationError("mqtt.tls.enabled must be a boolean")
    if not tls["enabled"]:
        if set(tls) != {"enabled"}:
            raise ConfigurationError("mqtt.tls must contain only enabled when disabled")
        return
    if set(tls) != {"enabled", "ca_certificate", "server_hostname"}:
        raise ConfigurationError("mqtt.tls requires CA certificate and server hostname")
    certificate = tls["ca_certificate"]
    if (
        not isinstance(certificate, str)
        or not 1 <= len(certificate) <= 16_384
        or not certificate.startswith("-----BEGIN CERTIFICATE-----")
        or not certificate.rstrip().endswith("-----END CERTIFICATE-----")
    ):
        raise ConfigurationError("mqtt.tls.ca_certificate must be one PEM certificate")
    try:
        certificate.encode("ascii")
    except UnicodeError as exc:
        raise ConfigurationError("mqtt.tls.ca_certificate must be ASCII PEM") from exc
    _hostname(tls["server_hostname"], "mqtt.tls.server_hostname")


def validate_config(config):
    if not isinstance(config, dict):
        raise ConfigurationError("configuration must be an object")
    for key in ("device_id", "environment", "serial", "ethernet", "wifi", "printer", "queue"):
        if key not in config:
            raise ConfigurationError(f"missing configuration field: {key}")
    device_id = config["device_id"]
    if not isinstance(device_id, str) or not 1 <= len(device_id) <= 64:
        raise ConfigurationError("device_id must be 1..64 characters")
    topic_characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-"
    if not all(character in topic_characters for character in device_id):
        raise ConfigurationError("device_id must be a safe MQTT topic segment")

    max_line = config["serial"].get("max_line_bytes")
    if not isinstance(max_line, int) or not 256 <= max_line <= 65_536:
        raise ConfigurationError("serial.max_line_bytes must be 256..65536")

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

    wifi = config["wifi"]
    if not isinstance(wifi, dict):
        raise ConfigurationError("wifi must be an object")
    if not isinstance(wifi.get("enabled"), bool):
        raise ConfigurationError("wifi.enabled must be a boolean")
    _ipv4(wifi.get("dns"), "wifi.dns", nullable=True)
    for field, minimum, maximum in (("ssid", 1, 32), ("password", 8, 64)):
        value = wifi.get(field)
        if not isinstance(value, str) or not minimum <= len(value) <= maximum:
            raise ConfigurationError(f"wifi.{field} must be {minimum}..{maximum} characters")
    wifi_retry = wifi.get("retry_interval_ms")
    if not isinstance(wifi_retry, int) or not 100 <= wifi_retry <= 60000:
        raise ConfigurationError("wifi.retry_interval_ms must be 100..60000")

    mqtt = config.get("mqtt")
    if mqtt is not None:
        if not isinstance(mqtt, dict):
            raise ConfigurationError("mqtt must be an object")
        if not isinstance(mqtt.get("enabled"), bool):
            raise ConfigurationError("mqtt.enabled must be a boolean")
        for field, limit in (("host", 253), ("client_id", 64), ("username", 64), ("password", 128)):
            value = mqtt.get(field)
            if not isinstance(value, str) or not 1 <= len(value) <= limit:
                raise ConfigurationError(f"mqtt.{field} must be 1..{limit} characters")
        if not isinstance(mqtt.get("port"), int) or not 1 <= mqtt["port"] <= 65535:
            raise ConfigurationError("mqtt.port must be 1..65535")
        if not isinstance(mqtt.get("topic_prefix"), str) or mqtt["topic_prefix"] != "v1/devices":
            raise ConfigurationError("mqtt.topic_prefix must be v1/devices")
        keepalive = mqtt.get("keepalive_seconds")
        if not isinstance(keepalive, int) or not 5 <= keepalive <= 120:
            raise ConfigurationError("mqtt.keepalive_seconds must be 5..120")
        retry_interval = mqtt.get("retry_interval_ms")
        if not isinstance(retry_interval, int) or not 100 <= retry_interval <= 60000:
            raise ConfigurationError("mqtt.retry_interval_ms must be 100..60000")
        max_message_bytes = mqtt.get("max_message_bytes")
        if (
            not isinstance(max_message_bytes, int)
            or isinstance(max_message_bytes, bool)
            or not 1024 <= max_message_bytes <= 65_536
        ):
            raise ConfigurationError("mqtt.max_message_bytes must be 1024..65536")
        allow_cut = mqtt.setdefault("allow_cut", False)
        if not isinstance(allow_cut, bool):
            raise ConfigurationError("mqtt.allow_cut must be a boolean")
        _tls_settings(mqtt)
        if mqtt["enabled"] and not wifi["enabled"]:
            raise ConfigurationError("mqtt requires wifi.enabled=true")
    return config


def load_config(path="config.json"):
    try:
        with open(path) as config_file:
            return validate_config(json.load(config_file))
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"unable to load configuration: {exc}") from exc


def redacted(config):
    try:
        value = json.loads(json.dumps(config))
    except (TypeError, ValueError) as exc:
        raise ConfigurationError("configuration is not JSON-compatible") from exc
    if "mqtt" in value:
        value["mqtt"]["password"] = "***"
        if value["mqtt"].get("tls", {}).get("enabled"):
            value["mqtt"]["tls"]["ca_certificate"] = "***"
    if "wifi" in value:
        value["wifi"]["password"] = "***"
    return value
