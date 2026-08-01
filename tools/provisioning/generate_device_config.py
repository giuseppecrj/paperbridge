import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--printer-host", required=True)
    parser.add_argument("--printer-port", type=int, default=9100)
    parser.add_argument("--output", type=Path, default=Path("config.json"))
    args = parser.parse_args()
    try:
        template = json.loads(Path("firmware/micropython/config.example.json").read_text())
        template["device_id"] = args.device_id
        template["printer"]["host"] = args.printer_host
        template["printer"]["port"] = args.printer_port
        args.output.write_text(json.dumps(template, indent=2) + "\n")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Unable to generate configuration: {exc}") from exc
    print(args.output)


if __name__ == "__main__":
    main()
