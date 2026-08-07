import sys

from .config import load_config
from .escpos import EscPosRenderer
from .ethernet import W5500LAN, EthernetError
from .job_service import JobService  # type: ignore[reportMissingImports]
from .mqtt_adapter import MqttTracer  # type: ignore[reportMissingImports]
from .print_coordinator import PrintCoordinator
from .printer_transport import PrinterTransport
from .rpc_commands import CommandRouter
from .serial_rpc import SerialRpcServer
from .wifi import WiFiStation  # type: ignore[reportMissingImports]


def build_app(reader=None, writer=None, config_path="config.json"):
    config = load_config(config_path)
    ethernet = W5500LAN(config)
    try:
        ethernet.initialize()
        ethernet.configure_static()
    except EthernetError as exc:
        ethernet.last_error = str(exc)
    transport = PrinterTransport(config)
    coordinator = PrintCoordinator(EscPosRenderer(), transport)
    job_service = JobService(config, coordinator)
    wifi = None
    if config["wifi"]["enabled"]:
        wifi = WiFiStation(config)
    router = CommandRouter(
        config,
        ethernet,
        coordinator,
        transport,
        wifi=wifi,
        job_service=job_service,
    )
    mqtt = None
    if config.get("mqtt", {}).get("enabled"):
        mqtt = MqttTracer(
            config,
            wifi,
            job_service=job_service,
            before_delivery=router.require_ethernet_link,
        )
        router.mqtt = mqtt
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


def _start_serial_server(server, thread_module=None):
    thread = thread_module or __import__("_thread")
    thread.start_new_thread(server.run_forever, ())


def run():
    server, wifi, mqtt = build_app()
    adapter = mqtt or wifi
    if adapter is None:
        server.run_forever()
        return
    _start_serial_server(server)
    _poll_network(adapter)
