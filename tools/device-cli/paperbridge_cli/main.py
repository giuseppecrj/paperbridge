import argparse
import json
import sys

from .output import emit
from .ports import PortSelectionError, likely_ports, resolve_port
from .serial_client import DeviceError, SerialClient


def _parser():
    parser = argparse.ArgumentParser(prog="paperbridge")
    parser.add_argument("--port", help="USB serial device (or PAPERBRIDGE_PORT)")
    parser.add_argument("--timeout", type=float, default=3.0)
    parser.add_argument("--json", action="store_true", dest="json_output")
    parser.add_argument("--request-id", help="Serial RPC request ID (generated when omitted)")
    groups = parser.add_subparsers(dest="group", required=True)

    ports = groups.add_parser("ports").add_subparsers(dest="action", required=True)
    ports.add_parser("list")

    device = groups.add_parser("device").add_subparsers(dest="action", required=True)
    device.add_parser("ping")
    device.add_parser("info")
    device.add_parser("reboot")

    config = groups.add_parser("config").add_subparsers(dest="action", required=True)
    config.add_parser("show")

    mqtt = groups.add_parser("mqtt").add_subparsers(dest="action", required=True)
    mqtt.add_parser("status")

    ethernet = groups.add_parser("ethernet").add_subparsers(dest="action", required=True)
    ethernet.add_parser("init")
    ethernet.add_parser("status")
    ethernet.add_parser("link-status")
    ethernet.add_parser("configure-static")

    printer = groups.add_parser("printer").add_subparsers(dest="action", required=True)
    printer.add_parser("endpoint")
    printer.add_parser("probe")
    print_test = printer.add_parser("print-test")
    print_test.add_argument("text")
    printer.add_parser("feed-test")
    cut_test = printer.add_parser("cut-test")
    cut_test.add_argument("--confirm", action="store_true", required=True)

    job = groups.add_parser("job").add_subparsers(dest="action", required=True)
    submit = job.add_parser("submit")
    submit.add_argument("job_file")
    submit.add_argument("--allow-cut", action="store_true")

    serial_group = groups.add_parser("serial").add_subparsers(dest="action", required=True)
    serial_group.add_parser("monitor")
    return parser


def _rpc(args):
    commands = {
        ("device", "ping"): ("system.ping", {}),
        ("device", "info"): ("system.info", {}),
        ("device", "reboot"): ("system.reboot", {}),
        ("config", "show"): ("config.show_redacted", {}),
        ("mqtt", "status"): ("mqtt.status", {}),
        ("ethernet", "init"): ("ethernet.initialize", {}),
        ("ethernet", "status"): ("ethernet.status", {}),
        ("ethernet", "link-status"): ("ethernet.link_status", {}),
        ("ethernet", "configure-static"): ("ethernet.configure_static", {}),
        ("printer", "endpoint"): ("printer.endpoint", {}),
        ("printer", "probe"): ("printer.probe", {}),
        ("printer", "feed-test"): ("printer.feed_test", {}),
        ("printer", "cut-test"): (
            "printer.cut_test",
            {"confirm": getattr(args, "confirm", False)},
        ),
    }
    if (args.group, args.action) == ("printer", "print-test"):
        return "printer.print_test", {"text": args.text}
    if (args.group, args.action) == ("job", "submit"):
        try:
            with open(args.job_file) as job_file:
                job = json.load(job_file)
        except (OSError, ValueError) as exc:
            raise DeviceError("INVALID_JOB_FILE", f"unable to read job file: {exc}") from exc
        return "job.submit", {"job": job, "allow_cut": args.allow_cut}
    return commands[(args.group, args.action)]


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if (args.group, args.action) == ("ports", "list"):
            ports = likely_ports()
            emit(ports, args.json_output)
            if not args.json_output and ports:
                if len(ports) == 1:
                    print(f"Use: export PAPERBRIDGE_PORT={ports[0]['device']}")
                else:
                    print("Use a device path above as PORT; VID/PID are identifiers only.")
            return 0
        port = resolve_port(args.port)
        with SerialClient(port, timeout=args.timeout) as client:
            if (args.group, args.action) == ("serial", "monitor"):
                client.monitor()
                return 0
            command, params = _rpc(args)
            emit(client.request(command, params, request_id=args.request_id), args.json_output)
            return 0
    except KeyboardInterrupt:
        return 130
    except (DeviceError, PortSelectionError, KeyError) as exc:
        code = getattr(exc, "code", "CLI_ERROR")
        if args.json_output:
            emit({"ok": False, "error": {"code": code, "message": str(exc)}}, True)
        else:
            print(f"{code}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
