import io
import json

import pytest
from src.serial_rpc import RpcError, SerialRpcServer, parse_request


def request(**overrides):
    value = {
        "type": "request",
        "request_id": "req-1",
        "command": "system.ping",
        "params": {},
    }
    value.update(overrides)
    return json.dumps(value)


def test_parses_valid_request():
    assert parse_request(request())["command"] == "system.ping"


@pytest.mark.parametrize("line", ["not json", "[]", '{"type":"request"}', b"\xff"])
def test_rejects_malformed_requests(line):
    with pytest.raises(RpcError) as error:
        parse_request(line)
    assert error.value.code == "INVALID_RPC_REQUEST"


def test_rejects_oversized_line():
    with pytest.raises(RpcError, match="maximum"):
        parse_request(request(params={"text": "x" * 100}), max_line_bytes=32)


def test_server_returns_stable_unsupported_command_error():
    output = io.StringIO()

    def dispatch(_command, _params):
        raise RpcError("UNSUPPORTED_RPC_COMMAND", "Unsupported")

    response = SerialRpcServer(io.StringIO(), output, dispatch).handle_line(request(command="nope"))
    assert response["error"]["code"] == "UNSUPPORTED_RPC_COMMAND"
    assert json.loads(output.getvalue())["request_id"] == "req-1"


def test_duplicate_request_id_replays_without_redispatching():
    output = io.StringIO()
    calls = []

    def dispatch(command, _params):
        calls.append(command)
        return {"status": "ok"}

    server = SerialRpcServer(io.StringIO(), output, dispatch)
    first = server.handle_line(request())
    second = server.handle_line(request())
    assert first == second
    assert calls == ["system.ping"]


def test_unexpected_dispatch_exception_maps_to_internal_error():
    output = io.StringIO()

    def dispatch(_command, _params):
        raise RuntimeError("boom")

    response = SerialRpcServer(io.StringIO(), output, dispatch).handle_line(request())
    assert response["ok"] is False
    assert response["error"]["code"] == "INTERNAL_ERROR"
    assert response["error"]["message"] == "Internal device error"


def test_serve_once_discards_the_remainder_of_an_oversized_line():
    output = io.StringIO()
    server = SerialRpcServer(
        io.StringIO("x" * 129 + "\n" + request() + "\n"), output, lambda *_args: {}
    )
    server.max_line_bytes = 128

    server.serve_once()
    response = server.serve_once()

    assert response is not None
    assert response["ok"] is True
    assert json.loads(output.getvalue().splitlines()[0])["error"]["code"] == "INVALID_RPC_REQUEST"
