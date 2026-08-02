import sys

from .config import load_config
from .escpos import EscPosRenderer
from .ethernet import W5500LAN
from .mqtt_adapter import MqttTracer  # type: ignore[reportMissingImports]
from .print_coordinator import PrintCoordinator
from .printer_transport import PrinterTransport
from .rpc_commands import CommandRouter
from .serial_rpc import SerialRpcServer


def build_app(reader=None, writer=None, config_path="config.json"):
    config = load_config(config_path)
    ethernet = W5500LAN(config)
    transport = PrinterTransport(config)
    coordinator = PrintCoordinator(EscPosRenderer(), transport)
    mqtt = None
    if config.get("mqtt", {}).get("enabled"):
        mqtt = MqttTracer(config, ethernet)
    router = CommandRouter(config, ethernet, coordinator, transport, mqtt=mqtt)
    server = SerialRpcServer(
        reader or sys.stdin,
        writer or sys.stdout,
        router.dispatch,
        config["serial"]["max_line_bytes"],
    )
    return server, mqtt


def _input_poller(reader):
    try:
        select = __import__("uselect")
    except ImportError:
        select = __import__("select")
    poller = select.poll()
    poller.register(reader, select.POLLIN)
    return poller


def _run_with_mqtt(server, mqtt, poller_factory=None):
    poller = (poller_factory or _input_poller)(server.reader)
    while True:
        mqtt.poll()
        if poller.poll(25):
            server.serve_once()


def run():
    server, mqtt = build_app()
    if mqtt is None:
        server.run_forever()
    else:
        _run_with_mqtt(server, mqtt)
