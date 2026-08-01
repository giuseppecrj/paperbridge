from .escpos import RenderError
from .printer_transport import TransportError
from .serial_rpc import RpcError
from .status import StatusTracker


class PrintCoordinator:
    def __init__(self, renderer, transport):
        self.renderer = renderer
        self.transport = transport

    def _send(self, render):
        tracker = StatusTracker()
        try:
            tracker.transition("validated")
            tracker.transition("rendering")
            payload = render()
            tracker.transition("connecting_to_printer")
            tracker.transition("sending_to_printer")
            result = self.transport.send(payload)
            tracker.transition("delivered_to_printer")
            return result
        except RenderError as exc:
            raise RpcError("ESC_POS_RENDER_FAILED", str(exc)) from exc
        except TransportError as exc:
            raise RpcError(exc.code, exc.message) from exc

    def print_test(self, text):
        return self._send(lambda: self.renderer.render_text_test(text))

    def feed_test(self):
        return self._send(self.renderer.render_feed_test)

    def cut_test(self):
        return self._send(self.renderer.render_cut_test)

    def execute(self, job):
        return self._send(lambda: self.renderer.render(job))
