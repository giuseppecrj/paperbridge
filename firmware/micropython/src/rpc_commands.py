from .config import load_config, redacted
from .device_info import memory_info, reset_cause, system_info
from .serial_rpc import RpcError


class CommandRouter:
    def __init__(self, config, ethernet, coordinator, transport, queue):
        self.config = config
        self.ethernet = ethernet
        self.coordinator = coordinator
        self.transport = transport
        self.queue = queue

    def dispatch(self, command, params):
        handlers = {
            "system.ping": self.system_ping,
            "system.info": self.system_info,
            "system.memory": self.system_memory,
            "system.reset_cause": self.system_reset_cause,
            "config.show_redacted": self.config_show,
            "config.reload": self.config_reload,
            "ethernet.initialize": self.ethernet_initialize,
            "ethernet.status": self.ethernet_status,
            "ethernet.link_status": self.ethernet_link_status,
            "ethernet.configure_static": self.ethernet_configure_static,
            "printer.endpoint": self.printer_endpoint,
            "printer.probe": self.printer_probe,
            "printer.print_test": self.printer_print_test,
            "printer.feed_test": self.printer_feed_test,
            "printer.cut_test": self.printer_cut_test,
            "printer.send_fixture": self.printer_send_fixture,
            "queue.status": self.queue_status,
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

    def config_reload(self, _params):
        updated = load_config()
        self.config.clear()
        self.config.update(updated)
        return {"status": "reloaded"}

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
        self._require_ethernet_link()
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

    def printer_send_fixture(self, params):
        if params.get("name") != "hello-world":
            raise RpcError("INVALID_RPC_REQUEST", "unknown fixture")
        self._require_ethernet_link()
        return self.coordinator.print_test("Hello from Paperbridge")

    def queue_status(self, _params):
        return self.queue.status()

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
