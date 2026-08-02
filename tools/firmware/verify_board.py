import argparse
import subprocess
import sys

from device_port import require_device_port

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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", required=True)
    args = parser.parse_args(argv)
    require_device_port(args.port)
    result = subprocess.run(
        [sys.executable, "-m", "mpremote", "connect", args.port, "exec", PROBE],
        check=False,
    )
    if result.returncode:
        raise SystemExit(
            "Unable to run the MicroPython probe. Confirm MicroPython is flashed "
            "and that no serial monitor is using the port."
        )


if __name__ == "__main__":
    main()
