import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

JOB_RESULT_ERROR_CODES = __import__(
    "src.constants", None, None, ("JOB_RESULT_ERROR_CODES",)
).JOB_RESULT_ERROR_CODES

SCHEMAS = Path("packages/protocol/schemas")
EXAMPLES = Path("packages/protocol/examples")
JOB_FIXTURES = Path("packages/protocol/fixtures/print-job-v1")
RESULT_FIXTURES = Path("packages/protocol/fixtures/job-result-v1")


def load(path):
    return json.loads(path.read_text())


def job_validator():
    return Draft202012Validator(load(SCHEMAS / "print-job.v1.schema.json"))


def result_validator():
    return Draft202012Validator(load(SCHEMAS / "job-result.v1.schema.json"))


def test_serial_ping_matches_schema():
    Draft202012Validator(load(SCHEMAS / "serial-request.v1.schema.json")).validate(
        load(EXAMPLES / "serial-ping.json")
    )


def test_print_job_schema_accepts_valid_and_rejects_raw_commands():
    validator = job_validator()
    validator.validate(load(EXAMPLES / "hello-world-job.json"))
    with pytest.raises(ValidationError):
        validator.validate(load(EXAMPLES / "invalid-job.json"))


@pytest.mark.parametrize(
    "name",
    [
        "valid-text-feed.json",
        "valid-rule.json",
        "valid-cut.json",
    ],
)
def test_print_job_schema_accepts_shared_valid_fixtures(name):
    job_validator().validate(load(JOB_FIXTURES / name))


@pytest.mark.parametrize(
    "name",
    [
        "invalid-raw-block.json",
        "invalid-control-text.json",
        "invalid-style-fields.json",
        "invalid-copies.json",
        "invalid-expires-at.json",
        "invalid-empty-text.json",
        "invalid-fractional-feed.json",
    ],
)
def test_print_job_schema_rejects_shared_invalid_fixtures(name):
    with pytest.raises(ValidationError):
        job_validator().validate(load(JOB_FIXTURES / name))


def test_print_job_schema_accepts_cut_requires_opt_in_policy_fixture():
    # Authorization fixture: schema-valid; device/render gate is separate.
    job_validator().validate(load(JOB_FIXTURES / "cut-requires-opt-in.json"))


def test_print_job_schema_rejects_boolean_feed_lines():
    base = load(JOB_FIXTURES / "valid-text-feed.json")
    payload = json.loads(json.dumps(base))
    payload["content"]["blocks"] = [{"type": "feed", "lines": True}]
    with pytest.raises(ValidationError):
        job_validator().validate(payload)


def test_print_job_transport_boundary_fixtures_remain_schema_valid():
    at_limit = JOB_FIXTURES / "valid-at-mqtt-limit.json"
    over_limit = JOB_FIXTURES / "schema-valid-over-mqtt-limit.json"
    assert len(at_limit.read_bytes()) == 1024
    assert len(over_limit.read_bytes()) == 1025
    job_validator().validate(load(at_limit))
    job_validator().validate(load(over_limit))


@pytest.mark.parametrize(
    "name",
    [
        "delivered.json",
        "rejected-validation.json",
        "transport-failure.json",
        "partial-write.json",
    ],
)
def test_job_result_schema_accepts_terminal_fixtures(name):
    result_validator().validate(load(RESULT_FIXTURES / name))


def test_job_result_schema_and_firmware_share_stable_error_codes():
    schema = load(SCHEMAS / "job-result.v1.schema.json")
    assert set(schema["properties"]["error_code"]["enum"]) == JOB_RESULT_ERROR_CODES


def test_print_job_schema_rejects_styling_and_options_fields():
    validator = job_validator()
    base = load(JOB_FIXTURES / "valid-text-feed.json")
    styled = json.loads(json.dumps(base))
    styled["content"]["blocks"][0]["bold"] = True
    with pytest.raises(ValidationError):
        validator.validate(styled)
    with_options = json.loads(json.dumps(base))
    with_options["options"] = {"copies": 1}
    with pytest.raises(ValidationError):
        validator.validate(with_options)
