import json

import pytest
from paperbridge_cli.serial_client import DeviceError, SerialClient


class FakeSerial:
    def __init__(self, *_args, fail=False, **_kwargs):
        self.lines = []
        self.requests = []
        self.fail = fail
        self.closed = False

    def write(self, payload):
        request = json.loads(payload)
        self.requests.append(request)
        self.lines.extend(
            [
                b"MicroPython boot noise\n",
                b'{"type":"log","message":"ready"}\n',
                json.dumps(
                    {
                        "type": "response",
                        "request_id": request["request_id"],
                        "ok": not self.fail,
                        **(
                            {"error": {"code": "TEST_ERROR", "message": "failed"}}
                            if self.fail
                            else {"result": {"status": "ok"}}
                        ),
                    }
                ).encode()
                + b"\n",
            ]
        )
        return len(payload)

    def flush(self):
        pass

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def close(self):
        self.closed = True


def test_correlates_response_and_ignores_non_rpc_lines():
    fake = FakeSerial()
    with SerialClient("fake", serial_factory=lambda *_args, **_kwargs: fake) as client:
        assert client.request("system.ping") == {"status": "ok"}
    assert fake.closed


def test_surfaces_structured_device_error():
    fake = FakeSerial(fail=True)
    with (
        SerialClient("fake", serial_factory=lambda *_args, **_kwargs: fake) as client,
        pytest.raises(DeviceError) as error,
    ):
        client.request("system.ping")
    assert error.value.code == "TEST_ERROR"


def test_allows_transport_request_id_to_differ_from_job_id():
    fake = FakeSerial()
    with SerialClient("fake", serial_factory=lambda *_args, **_kwargs: fake) as client:
        assert client.request(
            "job.submit",
            {"job": {"job_id": "job-1"}},
            request_id="request-1",
        ) == {"status": "ok"}
    assert fake.requests == [
        {
            "type": "request",
            "request_id": "request-1",
            "command": "job.submit",
            "params": {"job": {"job_id": "job-1"}},
        }
    ]
