import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from device_port import require_device_port


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args(argv)
    require_device_port(args.port)
    payload = args.firmware.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest.lower() != args.sha256.lower():
        raise SystemExit(f"SHA-256 mismatch: {digest}")
    print(f"firmware_sha256={digest}")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "esptool",
            "--port",
            args.port,
            "--baud",
            "460800",
            "write-flash",
            "0",
            str(args.firmware),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
