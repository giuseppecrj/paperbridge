import gc
import os
import sys

from .constants import FIRMWARE_VERSION


def _uname():
    try:
        value = os.uname()
        return {
            "sysname": value.sysname,
            "nodename": value.nodename,
            "release": value.release,
            "version": value.version,
            "machine": value.machine,
        }
    except (AttributeError, OSError):
        return {}


def memory_info():
    result = {"heap_free_bytes": getattr(gc, "mem_free", lambda: None)()}
    result["heap_allocated_bytes"] = getattr(gc, "mem_alloc", lambda: None)()
    return result


def reset_cause():
    try:
        machine = __import__("machine")
        return machine.reset_cause()
    except ImportError:
        return None


def system_info(config):
    implementation = sys.implementation
    version = getattr(implementation, "version", None)
    return {
        "firmware_version": FIRMWARE_VERSION,
        "device_id": config["device_id"],
        "implementation": implementation.name,
        "implementation_version": list(version) if version else None,
        "platform": sys.platform,
        "board": _uname(),
        "memory": memory_info(),
        "reset_cause": reset_cause(),
        "hardware_verified": False,
    }
