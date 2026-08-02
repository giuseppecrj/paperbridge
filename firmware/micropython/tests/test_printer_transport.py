from types import ModuleType

import pytest
from src.printer_transport import PrinterTransport, TransportError


class FakeSocket:
    def __init__(self, connect_error=None, write_error=None, write_sizes=None):
        self.connect_error = connect_error
        self.write_error = write_error
        self.write_sizes = list(write_sizes or [])
        self.closed = False
        self.sent = b""

    def settimeout(self, _value):
        return None

    def connect(self, _endpoint):
        if self.connect_error is not None:
            raise self.connect_error

    def send(self, payload):
        if self.write_error is not None:
            raise self.write_error
        if self.write_sizes:
            size = self.write_sizes.pop(0)
            if size == 0:
                return 0
            chunk = payload[:size]
            self.sent += chunk
            return len(chunk)
        self.sent += payload
        return len(payload)

    def close(self):
        self.closed = True


class FakeSocketModule(ModuleType):
    AF_INET = 2
    SOCK_STREAM = 1

    def __init__(self, sock):
        super().__init__("fake_socket")
        self.sock = sock

    def socket(self, _family, _kind):
        return self.sock


def transport(sock):
    config = {
        "printer": {
            "host": "192.168.1.87",
            "port": 9100,
            "connect_timeout_ms": 1000,
            "write_timeout_ms": 1000,
        }
    }
    return PrinterTransport(config, socket_module=FakeSocketModule(sock))


@pytest.mark.parametrize(
    ("error", "phase", "code"),
    [
        (OSError(110, "timed out"), "connect", "PRINTER_CONNECT_TIMEOUT"),
        (OSError(111, "refused"), "connect", "PRINTER_CONNECTION_REFUSED"),
        (OSError(104, "reset"), "connect", "PRINTER_CONNECTION_RESET"),
        (OSError(116, "write timeout"), "write", "PRINTER_WRITE_TIMEOUT"),
    ],
)
def test_maps_socket_errors(error, phase, code):
    if phase == "connect":
        sock = FakeSocket(connect_error=error)
        with pytest.raises(TransportError) as raised:
            transport(sock).probe()
    else:
        sock = FakeSocket(write_error=error)
        with pytest.raises(TransportError) as raised:
            transport(sock).send(b"hello")
    assert raised.value.code == code
    assert sock.closed is True


def test_partial_write_then_zero_is_connection_reset():
    sock = FakeSocket(write_sizes=[2, 0])
    with pytest.raises(TransportError) as raised:
        transport(sock).send(b"hello")
    assert raised.value.code == "PRINTER_CONNECTION_RESET"
    assert raised.value.bytes_sent == 2
    assert sock.closed is True


def test_send_delivers_full_payload():
    sock = FakeSocket(write_sizes=[2, 3])
    result = transport(sock).send(b"hello")
    assert result == {
        "status": "delivered_to_printer",
        "bytes_sent": 5,
        "printer_endpoint": "192.168.1.87:9100",
    }
    assert sock.sent == b"hello"
    assert sock.closed is True
