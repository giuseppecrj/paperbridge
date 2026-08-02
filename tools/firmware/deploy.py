import argparse
import subprocess
import sys
import time
from pathlib import Path

from device_port import require_device_port
from paperbridge_cli.serial_client import DeviceError, SerialClient

REPO_ROOT = Path(__file__).resolve().parents[2]


def firmware_root() -> Path:
    return REPO_ROOT / "firmware" / "micropython"


def source_files():
    return sorted((firmware_root() / "src").glob("*.py"))


def _command(port, *args):
    return [sys.executable, "-m", "mpremote", "connect", port, *args]


def ensure_micropython(port, run=subprocess.run):
    result = run(
        _command(port, "exec", "import sys; print(sys.implementation.name)"),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode or "micropython" not in getattr(result, "stdout", "").lower():
        raise SystemExit(
            "MicroPython raw REPL is unavailable on this port. "
            "Flash MicroPython before running `just deploy`."
        )


def mpremote(port, *args):
    if subprocess.run(_command(port, *args), check=False).returncode:
        raise SystemExit("mpremote command failed; see the error above")


def application_ping(port, client_factory=SerialClient):
    """Prove the deployed app answers system.ping over host SerialClient."""
    try:
        with client_factory(port, timeout=0.5, startup_timeout=0.5) as client:
            result = client.request("system.ping")
    except (DeviceError, OSError, TimeoutError, ValueError) as exc:
        raise SystemExit(f"application RPC not ready: {exc}") from exc
    if not isinstance(result, dict) or result.get("status") != "ok":
        raise SystemExit(f"application RPC not ready: unexpected ping result {result!r}")


def wait_for_ready(
    port,
    *,
    timeout_s=15.0,
    interval_s=0.5,
    sleep=time.sleep,
    path_exists=None,
    probe=None,
):
    """Bounded wait for USB re-enumeration and application readiness after reset."""
    path_exists = path_exists or (lambda p: Path(p).exists())
    probe = probe or application_ping
    deadline = time.monotonic() + timeout_s
    last_error = "device path missing or application not ready"
    while time.monotonic() < deadline:
        if path_exists(port):
            try:
                probe(port)
                return
            except SystemExit as exc:
                message = str(exc)
                if message:
                    last_error = message
        sleep(interval_s)
    raise SystemExit(f"Device not ready on {port} within {timeout_s:.0f}s: {last_error}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args(argv)
    require_device_port(args.port)
    root = firmware_root()
    config = root / "config.json"
    if not config.exists():
        raise SystemExit(f"Create {config} from config.example.json before deploying")
    ensure_micropython(args.port)
    mpremote(
        args.port,
        "exec",
        "import os\ntry: os.mkdir('src')\nexcept OSError: pass",
    )
    mpremote(args.port, "fs", "--force", "cp", str(root / "boot.py"), ":boot.py")
    mpremote(
        args.port,
        "fs",
        "--force",
        "cp",
        *(str(path) for path in source_files()),
        ":src/",
    )
    mpremote(args.port, "fs", "--force", "cp", str(config), ":config.json")
    mpremote(args.port, "fs", "--force", "cp", str(root / "main.py"), ":main.py")
    mpremote(args.port, "reset")
    wait_for_ready(args.port)


if __name__ == "__main__":
    main()
