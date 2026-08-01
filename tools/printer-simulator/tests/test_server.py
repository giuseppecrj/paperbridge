import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "paperbridge_printer_simulator", Path("tools/printer-simulator/server.py")
)
assert SPEC is not None and SPEC.loader is not None
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


def test_capture_records_payload_and_sha256(tmp_path):
    metadata = server.CaptureStore(tmp_path).record(b"hello", ("127.0.0.1", 1234))
    assert metadata["bytes"] == 5
    assert metadata["sha256"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    assert Path(metadata["path"]).read_bytes() == b"hello"
