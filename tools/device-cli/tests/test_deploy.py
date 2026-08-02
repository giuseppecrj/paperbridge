import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SPEC = importlib.util.spec_from_file_location(
    "paperbridge_deploy", Path("tools/firmware/deploy.py")
)
assert SPEC is not None and SPEC.loader is not None
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)


def test_source_files_exclude_host_bytecode():
    files = deploy.source_files()
    assert files
    assert all(path.suffix == ".py" for path in files)
    assert all("__pycache__" not in path.parts for path in files)


def test_preflight_explains_that_micropython_must_be_flashed():
    result = SimpleNamespace(returncode=1)

    with pytest.raises(SystemExit, match="Flash MicroPython before running `just deploy`"):
        deploy.ensure_micropython("/dev/cu.usbmodem101", run=lambda *_args, **_kwargs: result)
