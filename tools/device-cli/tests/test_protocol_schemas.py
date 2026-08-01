import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

SCHEMAS = Path("packages/protocol/schemas")
EXAMPLES = Path("packages/protocol/examples")


def load(path):
    return json.loads(path.read_text())


def test_serial_ping_matches_schema():
    Draft202012Validator(load(SCHEMAS / "serial-request.v1.schema.json")).validate(
        load(EXAMPLES / "serial-ping.json")
    )


def test_print_job_schema_accepts_valid_and_rejects_raw_commands():
    validator = Draft202012Validator(
        load(SCHEMAS / "print-job.v1.schema.json"), format_checker=FormatChecker()
    )
    validator.validate(load(EXAMPLES / "hello-world-job.json"))
    with pytest.raises(ValidationError):
        validator.validate(load(EXAMPLES / "invalid-job.json"))
