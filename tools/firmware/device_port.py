from pathlib import Path


def require_device_port(port: str) -> str:
    """Reject empty, VID/PID-style, or missing device paths. Never guess a port."""
    if not port or not str(port).strip():
        raise SystemExit("PORT must be a nonempty device path (for example /dev/cu.usbmodem101)")
    port = str(port).strip()
    if port.isdigit():
        raise SystemExit(
            "PORT must be the device path from `just ports` "
            "(for example /dev/cu.usbmodem101), not the VID/PID"
        )
    if not Path(port).exists():
        raise SystemExit(f"Serial device does not exist: {port}")
    return port
