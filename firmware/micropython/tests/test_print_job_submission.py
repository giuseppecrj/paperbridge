import importlib.util
import io
import json
import socket
import threading
from pathlib import Path
from types import SimpleNamespace

from src.escpos import EscPosRenderer
from src.print_coordinator import PrintCoordinator
from src.printer_transport import PrinterTransport
from src.rpc_commands import CommandRouter
from src.serial_rpc import SerialRpcServer

SIMULATOR_SPEC = importlib.util.spec_from_file_location(
    "paperbridge_printer_simulator", Path("tools/printer-simulator/server.py")
)
assert SIMULATOR_SPEC is not None and SIMULATOR_SPEC.loader is not None
simulator = importlib.util.module_from_spec(SIMULATOR_SPEC)
SIMULATOR_SPEC.loader.exec_module(simulator)


class LinkedEthernet:
    def status(self):
        return {"link_up": True}


def available_port():
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        return reserved.getsockname()[1]


def test_serial_job_submission_replays_request_id_and_captures_semantic_bytes(tmp_path):
    port = available_port()
    args = SimpleNamespace(
        host="127.0.0.1",
        port=port,
        capture_dir=tmp_path,
        accept_delay=0,
        read_delay=0,
        read_size=1024,
        close_after=0,
        reset_after=0,
    )
    ready = threading.Event()
    thread = threading.Thread(target=simulator.serve, args=(args, 1, ready), daemon=True)
    thread.start()
    assert ready.wait(1)

    config = {
        "device_id": "paperbridge-dev-001",
        "printer": {
            "host": "127.0.0.1",
            "port": port,
            "connect_timeout_ms": 1000,
            "write_timeout_ms": 1000,
        },
    }
    transport = PrinterTransport(config)
    router = CommandRouter(
        config,
        LinkedEthernet(),
        PrintCoordinator(EscPosRenderer(), transport),
        transport,
    )
    job_path = Path("packages/protocol/fixtures/print-job-v1/valid-text-feed.json")
    job = json.loads(job_path.read_text())
    request = json.dumps(
        {
            "type": "request",
            "request_id": "request-1",
            "command": "job.submit",
            "params": {"job": job, "allow_cut": False},
        }
    )
    rpc = SerialRpcServer(io.StringIO(), io.StringIO(), router.dispatch)

    first = rpc.handle_line(request)
    second = rpc.handle_line(request)
    thread.join(1)

    assert first == second
    assert first["result"]["job_id"] == "job-hello-001"
    assert first["result"]["status"] == "delivered_to_printer"
    assert not thread.is_alive()
    assert [capture.read_bytes() for capture in tmp_path.glob("*.bin")] == [
        b"\x1b@Hello from Paperbridge\n\n\n\n"
    ]
