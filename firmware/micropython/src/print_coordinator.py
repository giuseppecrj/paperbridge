from .escpos import RenderError
from .printer_transport import TransportError
from .serial_rpc import RpcError
from .status import StatusTracker


class PrintCoordinator:
    def __init__(self, renderer, transport, lock=None):
        self.renderer = renderer
        self.transport = transport
        self._lock = lock or __import__("_thread").allocate_lock()

    def _send(self, render):
        self._lock.acquire()
        try:
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
                raise RpcError(exc.code, str(exc)) from exc
            except TransportError as exc:
                raise RpcError(exc.code, exc.message, bytes_sent=exc.bytes_sent) from exc
        finally:
            self._lock.release()

    def print_test(self, text):
        return self._send(lambda: self.renderer.render_text_test(text))

    def feed_test(self):
        return self._send(self.renderer.render_feed_test)

    def cut_test(self):
        return self._send(self.renderer.render_cut_test)

    def print_job(self, job, allow_cut=False):
        result = self._send(lambda: self.renderer.render(job, allow_cut=allow_cut))
        result["job_id"] = job["job_id"]
        return result
