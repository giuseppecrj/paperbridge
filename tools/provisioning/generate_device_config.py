import argparse
import json
import os
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = REPO_ROOT / "firmware" / "micropython" / "config.example.json"


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is required")
    return value


def integer_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer") from exc


def boolean_env(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    if value == "true":
        return True
    if value == "false":
        return False
    raise SystemExit(f"{name} must be true or false")


def apply_environment(template):
    device_id = required_env("PAPERBRIDGE_DEVICE_ID")
    template["device_id"] = device_id
    template["printer"]["host"] = required_env("PAPERBRIDGE_PRINTER_HOST")
    template["printer"]["port"] = integer_env("PAPERBRIDGE_PRINTER_PORT", 9100)
    template["wifi"].update(
        enabled=True,
        ssid=required_env("PAPERBRIDGE_WIFI_SSID"),
        password=required_env("PAPERBRIDGE_WIFI_PASSWORD"),
    )
    template["mqtt"].update(
        enabled=True,
        host=required_env("PAPERBRIDGE_MQTT_HOST"),
        port=integer_env("PAPERBRIDGE_MQTT_PORT", 1883),
        client_id=device_id,
        username=required_env("PAPERBRIDGE_MQTT_USERNAME"),
        password=required_env("PAPERBRIDGE_MQTT_PASSWORD"),
        allow_cut=boolean_env("PAPERBRIDGE_MQTT_ALLOW_CUT", False),
    )


def write_config(path, template):
    content = json.dumps(template, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
        encoding="utf-8",
    ) as config_file:
        temp_path = Path(config_file.name)
        os.fchmod(config_file.fileno(), 0o600)
        config_file.write(content)
    try:
        os.replace(temp_path, path)
    except OSError:
        temp_path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-env", action="store_true")
    parser.add_argument("--device-id")
    parser.add_argument("--printer-host")
    parser.add_argument("--printer-port", type=int, default=9100)
    parser.add_argument("--output", type=Path, default=Path("config.json"))
    args = parser.parse_args(argv)
    if not args.from_env and (not args.device_id or not args.printer_host):
        parser.error("--device-id and --printer-host are required without --from-env")
    try:
        template = json.loads(EXAMPLE.read_text())
        if args.from_env:
            apply_environment(template)
        else:
            template["device_id"] = args.device_id
            template["printer"]["host"] = args.printer_host
            template["printer"]["port"] = args.printer_port
        args.output.parent.mkdir(parents=True, exist_ok=True)
        write_config(args.output, template)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Unable to generate configuration: {exc}") from exc
    print(args.output)


if __name__ == "__main__":
    main()
