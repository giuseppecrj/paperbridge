import argparse
import subprocess
import sys
from pathlib import Path

PROBE = """import gc, json, machine, network, os, sys
print(json.dumps({
 'implementation': sys.implementation.name,
 'version': list(sys.implementation.version),
 'platform': sys.platform,
 'uname': list(os.uname()),
 'reset_cause': machine.reset_cause(),
 'heap_free_bytes': gc.mem_free(),
 'phy_w5500': hasattr(network, 'PHY_W5500'),
 'lan': hasattr(network, 'LAN'),
}))
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args()
    if args.port.isdigit():
        raise SystemExit(
            "PORT must be the device path from `just ports` "
            "(for example /dev/cu.usbmodem101), not the VID/PID"
        )
    if args.port.startswith("/dev/") and not Path(args.port).exists():
        raise SystemExit(f"Serial device does not exist: {args.port}")
    try:
        subprocess.run(
            [sys.executable, "-m", "mpremote", "connect", args.port, "exec", PROBE],
            check=True,
        )
    except subprocess.CalledProcessError:
        raise SystemExit(
            "Unable to run the MicroPython probe. Confirm MicroPython is flashed "
            "and that no serial monitor is using the port."
        ) from None


if __name__ == "__main__":
    main()
