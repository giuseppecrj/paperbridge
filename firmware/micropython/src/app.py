import sys

from .config import load_config
from .escpos import EscPosRenderer
from .ethernet import W5500LAN
from .mqtt_adapter import MqttTracer  # type: ignore[reportMissingImports]
from .print_coordinator import PrintCoordinator
from .printer_transport import PrinterTransport
from .rpc_commands import CommandRouter
from .serial_rpc import SerialRpcServer
from .wifi import WiFiStation  # type: ignore[reportMissingImports]


def build_app(reader=None, writer=None, config_path="config.json"):
    config = load_config(config_path)
    ethernet = W5500LAN(config)
    transport = PrinterTransport(config)
    coordinator = PrintCoordinator(EscPosRenderer(), transport)
    wifi = None
    if config["wifi"]["enabled"]:
        wifi = WiFiStation(config)
    mqtt = None
    if config.get("mqtt", {}).get("enabled"):
        mqtt = MqttTracer(config, wifi)
    router = CommandRouter(config, ethernet, coordinator, transport, mqtt=mqtt, wifi=wifi)
    server = SerialRpcServer(
        reader or sys.stdin,
        writer or sys.stdout,
        router.dispatch,
        config["serial"]["max_line_bytes"],
    )
    return server, wifi, mqtt


def _poll_network(adapter):
    time = __import__("time")
    sleep_ms = getattr(time, "sleep_ms", None)
    while True:
        try:
            adapter.poll()
        except Exception as exc:
            adapter.record_error(f"NETWORK_THREAD_FAILED: {exc}")
        if sleep_ms:
            sleep_ms(25)
        else:
            time.sleep(0.025)


def _start_network_poller(adapter, thread_module=None):
    try:
        thread = thread_module or __import__("_thread")
        thread.start_new_thread(_poll_network, (adapter,))
    except Exception as exc:
        adapter.record_error(f"NETWORK_THREAD_START_FAILED: {exc}")
        return False
    return True


def run():
    server, wifi, mqtt = build_app()
    adapter = mqtt or wifi
    if adapter is not None:
        _start_network_poller(adapter)
    server.run_forever()
