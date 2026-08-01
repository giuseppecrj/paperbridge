import socket


class TransportError(Exception):
    def __init__(self, code, message, bytes_sent=0):
        super().__init__(message)
        self.code = code
        self.message = message
        self.bytes_sent = bytes_sent


def _map_socket_error(exc, phase):
    number = exc.args[0] if exc.args and isinstance(exc.args[0], int) else None
    if number in (60, 110, 116):
        code = "PRINTER_CONNECT_TIMEOUT" if phase == "connect" else "PRINTER_WRITE_TIMEOUT"
    elif number in (61, 111):
        code = "PRINTER_CONNECTION_REFUSED"
    elif number in (54, 104):
        code = "PRINTER_CONNECTION_RESET"
    else:
        code = "PRINTER_CONNECTION_RESET"
    return TransportError(code, f"Printer socket {phase} failed")


class PrinterTransport:
    def __init__(self, config, socket_module=socket):
        self.config = config
        self.socket_module = socket_module

    def endpoint(self):
        printer = self.config["printer"]
        return f"{printer['host']}:{printer['port']}"

    def _connect(self):
        printer = self.config["printer"]
        sock = self.socket_module.socket(self.socket_module.AF_INET, self.socket_module.SOCK_STREAM)
        sock.settimeout(printer["connect_timeout_ms"] / 1000)
        try:
            sock.connect((printer["host"], printer["port"]))
            sock.settimeout(printer["write_timeout_ms"] / 1000)
            return sock
        except OSError as exc:
            sock.close()
            raise _map_socket_error(exc, "connect") from exc

    def probe(self):
        sock = self._connect()
        sock.close()
        return {"reachable": True, "printer_endpoint": self.endpoint()}

    def send(self, payload):
        sock = self._connect()
        sent = 0
        try:
            while sent < len(payload):
                written = sock.send(payload[sent:])
                if not written:
                    raise TransportError(
                        "PRINTER_CONNECTION_RESET", "Printer closed during write", sent
                    )
                sent += written
        except TransportError:
            raise
        except OSError as exc:
            error = _map_socket_error(exc, "write")
            error.bytes_sent = sent
            raise error from exc
        finally:
            sock.close()
        return {
            "status": "delivered_to_printer",
            "bytes_sent": sent,
            "printer_endpoint": self.endpoint(),
        }
