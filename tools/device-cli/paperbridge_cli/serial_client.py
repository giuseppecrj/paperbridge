import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import serial


class DeviceError(RuntimeError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class SerialClient:
    def __init__(
        self,
        port,
        timeout=3.0,
        startup_timeout=10.0,
        serial_factory: Callable[..., Any] = serial.Serial,
    ):
        self.port = port
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.serial_factory = serial_factory
        self.serial = None

    def __enter__(self):
        deadline = time.monotonic() + self.startup_timeout
        last_error = None
        while time.monotonic() < deadline:
            try:
                self.serial = self.serial_factory(
                    self.port,
                    baudrate=115200,
                    timeout=min(self.timeout, 0.25),
                    write_timeout=self.timeout,
                )
                return self
            except serial.SerialException as exc:
                last_error = exc
                time.sleep(0.25)
        raise DeviceError("SERIAL_OPEN_FAILED", f"Unable to open {self.port}: {last_error}")

    def __exit__(self, exc_type, exc_value, traceback):
        if self.serial is not None:
            self.serial.close()

    def _connection(self):
        if self.serial is None:
            raise DeviceError("SERIAL_NOT_OPEN", "Serial client is not open")
        return self.serial

    def request(self, command, params=None, request_id=None):
        request_id = request_id or "req-" + uuid.uuid4().hex
        request = {
            "type": "request",
            "request_id": request_id,
            "command": command,
            "params": params or {},
        }
        connection = self._connection()
        try:
            connection.write((json.dumps(request, separators=(",", ":")) + "\n").encode())
            connection.flush()
        except (serial.SerialException, serial.SerialTimeoutException) as exc:
            raise DeviceError("SERIAL_WRITE_FAILED", str(exc)) from exc

        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            try:
                line = connection.readline()
            except serial.SerialException as exc:
                raise DeviceError("SERIAL_READ_FAILED", str(exc)) from exc
            if not line:
                continue
            if len(line) > 65536:
                raise DeviceError("INVALID_RPC_RESPONSE", "Device response exceeded 65536 bytes")
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeError, ValueError):
                continue  # Boot/REPL noise is not an RPC response.
            if message.get("type") != "response" or message.get("request_id") != request_id:
                continue
            if not message.get("ok"):
                error = message.get("error", {})
                raise DeviceError(error.get("code", "DEVICE_ERROR"), error.get("message", "Error"))
            return message.get("result", {})
        raise DeviceError("SERIAL_RESPONSE_TIMEOUT", f"No response to {command} from {self.port}")

    def monitor(self):
        connection = self._connection()
        while True:
            line = connection.readline()
            if line:
                print(line.decode("utf-8", errors="replace"), end="")
