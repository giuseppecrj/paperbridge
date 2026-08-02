from .config import redacted
from .device_info import memory_info, reset_cause, system_info
from .job_service import JobService  # type: ignore[reportMissingImports]
from .serial_rpc import RpcError


class CommandRouter:
    def __init__(
        self,
        config,
        ethernet,
        coordinator,
        transport,
        mqtt=None,
        wifi=None,
        job_service=None,
    ):
        self.config = config
        self.ethernet = ethernet
        self.coordinator = coordinator
        self.transport = transport
        self.mqtt = mqtt
        self.wifi = wifi
        self.job_service = job_service or JobService(config, coordinator)

    def dispatch(self, command, params):
        handlers = {
            "system.ping": self.system_ping,
            "system.info": self.system_info,
            "system.memory": self.system_memory,
            "system.reset_cause": self.system_reset_cause,
            "config.show_redacted": self.config_show,
            "wifi.status": self.wifi_status,
            "wifi.disconnect": self.wifi_disconnect,
            "wifi.reconnect": self.wifi_reconnect,
            "mqtt.status": self.mqtt_status,
            "ethernet.initialize": self.ethernet_initialize,
            "ethernet.status": self.ethernet_status,
            "ethernet.link_status": self.ethernet_link_status,
            "ethernet.configure_static": self.ethernet_configure_static,
            "printer.endpoint": self.printer_endpoint,
            "printer.probe": self.printer_probe,
            "printer.print_test": self.printer_print_test,
            "printer.feed_test": self.printer_feed_test,
            "printer.cut_test": self.printer_cut_test,
            "job.submit": self.job_submit,
            "system.reboot": self.system_reboot,
        }
        handler = handlers.get(command)
        if handler is None:
            raise RpcError("UNSUPPORTED_RPC_COMMAND", f"Unsupported command: {command}")
        return handler(params)

    def system_ping(self, _params):
        return {"status": "ok"}

    def system_info(self, _params):
        return system_info(self.config)

    def system_memory(self, _params):
        return memory_info()

    def system_reset_cause(self, _params):
        return {"reset_cause": reset_cause()}

    def config_show(self, _params):
        return redacted(self.config)

    def wifi_status(self, _params):
        if self.wifi is None:
            return {"enabled": False, "connected": False, "last_error": None}
        return self.wifi.status()

    def _require_wifi_confirmation(self, params):
        wifi = self.wifi
        if wifi is None:
            raise RpcError("WIFI_DISABLED", "station Wi-Fi is not configured")
        confirm = params.get("confirm")
        if not isinstance(confirm, bool) or not confirm:
            raise RpcError("INVALID_RPC_REQUEST", "Wi-Fi control requires confirm=true")
        return wifi

    def wifi_disconnect(self, params):
        return self._require_wifi_confirmation(params).disconnect()

    def wifi_reconnect(self, params):
        return self._require_wifi_confirmation(params).reconnect()

    def mqtt_status(self, _params):
        if self.mqtt is None:
            return {"enabled": False, "connected": False, "last_error": None}
        return self.mqtt.status()

    def ethernet_initialize(self, _params):
        try:
            return self.ethernet.initialize()
        except Exception as exc:
            raise RpcError("ETHERNET_INITIALIZATION_FAILED", str(exc)) from exc

    def ethernet_status(self, _params):
        return self.ethernet.status()

    def ethernet_link_status(self, _params):
        status = self.ethernet.status()
        return {"link_up": status["link_up"], "raw_status": status.get("raw_status")}

    def ethernet_configure_static(self, _params):
        try:
            return self.ethernet.configure_static()
        except Exception as exc:
            raise RpcError("INVALID_CONFIGURATION", str(exc)) from exc

    def printer_endpoint(self, _params):
        return {"printer_endpoint": self.transport.endpoint()}

    def _require_ethernet_link(self):
        if not self.ethernet.status().get("link_up"):
            raise RpcError("ETHERNET_LINK_DOWN", "W5500 physical link is down")

    def printer_probe(self, _params):
        try:
            return self.transport.probe()
        except Exception as exc:
            code = getattr(exc, "code", "INTERNAL_ERROR")
            raise RpcError(code, str(exc)) from exc

    def printer_print_test(self, params):
        self._require_ethernet_link()
        return self.coordinator.print_test(params.get("text"))

    def printer_feed_test(self, _params):
        self._require_ethernet_link()
        return self.coordinator.feed_test()

    def printer_cut_test(self, params):
        confirm = params.get("confirm")
        if not isinstance(confirm, bool) or not confirm:
            raise RpcError("INVALID_RPC_REQUEST", "cut test requires confirm=true")
        self._require_ethernet_link()
        return self.coordinator.cut_test()

    def job_submit(self, params):
        job = params.get("job")
        allow_cut = params.get("allow_cut", False)
        if not isinstance(allow_cut, bool):
            raise RpcError("INVALID_RPC_REQUEST", "allow_cut must be a boolean")
        return self.job_service.submit(
            job,
            allow_cut=allow_cut,
            before_delivery=self._require_ethernet_link,
        )

    def system_reboot(self, _params):
        try:
            machine = __import__("machine")
            timer = machine.Timer(-1)
            timer.init(
                period=250,
                mode=machine.Timer.ONE_SHOT,
                callback=lambda _timer: machine.reset(),
            )
        except ImportError as exc:
            raise RpcError("INTERNAL_ERROR", "reboot is available only on device") from exc
        return {"status": "reboot_scheduled"}
