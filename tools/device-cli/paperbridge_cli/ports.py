import glob
import os
from fnmatch import fnmatch

from serial.tools import list_ports

PORT_PATTERNS = (
    "/dev/cu.usbmodem*",
    "/dev/cu.usbserial*",
    "/dev/cu.wchusbserial*",
)


class PortSelectionError(RuntimeError):
    pass


def likely_ports():
    candidates = (
        port
        for port in list_ports.comports()
        if port.vid is not None or any(fnmatch(port.device, pattern) for pattern in PORT_PATTERNS)
    )
    devices = {
        port.device: {
            "device": port.device,
            "description": port.description,
            "vid": port.vid,
            "pid": port.pid,
        }
        for port in candidates
    }
    for pattern in PORT_PATTERNS:
        for device in glob.glob(pattern):
            devices.setdefault(
                device,
                {"device": device, "description": None, "vid": None, "pid": None},
            )
    return [devices[device] for device in sorted(devices)]


def resolve_port(explicit=None, environ=os.environ):
    selected = explicit or environ.get("PAPERBRIDGE_PORT")
    if selected:
        return selected
    ports = likely_ports()
    if not ports:
        raise PortSelectionError("No likely USB serial ports found; pass --port")
    if len(ports) > 1:
        names = ", ".join(port["device"] for port in ports)
        raise PortSelectionError("Multiple USB serial ports found; pass --port: " + names)
    return ports[0]["device"]
