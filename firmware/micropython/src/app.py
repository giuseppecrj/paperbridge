import sys

from .config import load_config
from .escpos import EscPosRenderer
from .ethernet import W5500LAN
from .print_coordinator import PrintCoordinator
from .printer_transport import PrinterTransport
from .rpc_commands import CommandRouter
from .serial_rpc import SerialRpcServer


def build_app(reader=None, writer=None, config_path="config.json"):
    config = load_config(config_path)
    transport = PrinterTransport(config)
    coordinator = PrintCoordinator(EscPosRenderer(), transport)
    router = CommandRouter(config, W5500LAN(config), coordinator, transport)
    return SerialRpcServer(
        reader or sys.stdin,
        writer or sys.stdout,
        router.dispatch,
        config["serial"]["max_line_bytes"],
    )


def run():
    build_app().run_forever()
