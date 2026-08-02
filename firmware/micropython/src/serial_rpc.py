import json

from .constants import DEFAULT_MAX_LINE_BYTES


class RpcError(Exception):
    def __init__(self, code, message, bytes_sent=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.bytes_sent = bytes_sent


def _line_complete(line):
    if isinstance(line, bytes):
        return line.endswith(b"\n")
    return line.endswith("\n")


def error_response(request_id, code, message):
    return {
        "type": "response",
        "request_id": request_id,
        "ok": False,
        "error": {"code": code, "message": message},
    }


def parse_request(line, max_line_bytes=DEFAULT_MAX_LINE_BYTES):
    if isinstance(line, str):
        encoded = line.encode("utf-8")
    elif isinstance(line, bytes):
        encoded = line
    else:
        raise RpcError("INVALID_RPC_REQUEST", "RPC line must be bytes or text")
    if len(encoded) > max_line_bytes:
        raise RpcError("INVALID_RPC_REQUEST", "RPC line exceeds maximum length")
    try:
        request = json.loads(encoded.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise RpcError("INVALID_RPC_REQUEST", "RPC line must be valid UTF-8 JSON") from None
    if not isinstance(request, dict):
        raise RpcError("INVALID_RPC_REQUEST", "RPC request must be an object")
    if request.get("type") != "request":
        raise RpcError("INVALID_RPC_REQUEST", "type must be request")
    request_id = request.get("request_id")
    command = request.get("command")
    if not isinstance(request_id, str) or not 1 <= len(request_id) <= 128:
        raise RpcError("INVALID_RPC_REQUEST", "request_id must be 1..128 characters")
    if not isinstance(command, str) or not command:
        raise RpcError("INVALID_RPC_REQUEST", "command must be a non-empty string")
    params = request.get("params", {})
    if not isinstance(params, dict):
        raise RpcError("INVALID_RPC_REQUEST", "params must be an object")
    return request


class SerialRpcServer:
    def __init__(
        self,
        reader,
        writer,
        dispatch,
        max_line_bytes=DEFAULT_MAX_LINE_BYTES,
        max_cached_responses=32,
    ):
        self.reader = reader
        self.writer = writer
        self.dispatch = dispatch
        self.max_line_bytes = max_line_bytes
        self.max_cached_responses = max_cached_responses
        self._responses = {}
        self._response_ids = []

    def _cache(self, request_id, response):
        self._responses[request_id] = response
        self._response_ids.append(request_id)
        if len(self._response_ids) > self.max_cached_responses:
            del self._responses[self._response_ids.pop(0)]

    def handle_line(self, line):
        request_id = None
        try:
            request = parse_request(line, self.max_line_bytes)
            request_id = request["request_id"]
            response = self._responses.get(request_id)
            if response is None:
                result = self.dispatch(request["command"], request["params"])
                response = {
                    "type": "response",
                    "request_id": request_id,
                    "ok": True,
                    "result": result or {},
                }
        except RpcError as exc:
            response = error_response(request_id, exc.code, exc.message)
        except Exception:
            response = error_response(request_id, "INTERNAL_ERROR", "Internal device error")
        if request_id is not None and request_id not in self._responses:
            self._cache(request_id, response)
        self.writer.write(json.dumps(response) + "\n")
        return response

    def serve_once(self):
        line = self.reader.readline(self.max_line_bytes + 1)
        if not line:
            return None
        if len(line) > self.max_line_bytes and not _line_complete(line):
            while True:
                remainder = self.reader.readline(self.max_line_bytes + 1)
                if not remainder or _line_complete(remainder):
                    break
        return self.handle_line(line)

    def run_forever(self):
        while True:
            self.serve_once()
