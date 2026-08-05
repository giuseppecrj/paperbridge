import json
from pathlib import Path

import pytest
from src.job_schema import JobValidationError, validate_job

FIXTURES = Path("packages/protocol/fixtures/print-job-v1")


def load(name):
    return json.loads((FIXTURES / name).read_text())


def job(block, **extra):
    payload = {
        "schema_version": "1",
        "job_id": "job-1",
        "device_id": "device-1",
        "created_at": "2026-08-01T00:00:00Z",
        "content": {"kind": "receipt", "blocks": [block]},
    }
    payload.update(extra)
    return payload


def test_accepts_bounded_text_job():
    assert validate_job(job({"type": "text", "text": "Hello"}))["job_id"] == "job-1"


def test_accepts_bounded_qr_module_size():
    assert (
        validate_job(job({"type": "qr", "data": "https://example.com", "module_size": 8}))["job_id"]
        == "job-1"
    )


def test_accepts_consistent_prepared_raster():
    assert (
        validate_job(job({"type": "raster", "width": 8, "height": 1, "data_base64": "qg=="}))[
            "job_id"
        ]
        == "job-1"
    )


@pytest.mark.parametrize(
    "name",
    [
        "valid-text-feed.json",
        "valid-rule.json",
        "valid-styled-text.json",
        "valid-qr.json",
        "valid-qr-sized.json",
        "valid-rich-receipt.json",
    ],
)
def test_shared_valid_fixtures_pass(name):
    assert validate_job(load(name))["schema_version"] == "1"


def test_shared_cut_fixture_requires_opt_in():
    cut_job = load("valid-cut.json")
    with pytest.raises(JobValidationError, match="allow_cut"):
        validate_job(cut_job)
    assert validate_job(cut_job, allow_cut=True)["job_id"] == "job-cut-001"


@pytest.mark.parametrize(
    "name",
    [
        "invalid-raw-block.json",
        "invalid-control-text.json",
        "invalid-qr-control-data.json",
        "invalid-qr-oversized.json",
        "invalid-oversized-text.json",
        "invalid-style-alignment.json",
        "invalid-style-multiplier.json",
        "invalid-copies.json",
        "invalid-expires-at.json",
        "invalid-empty-text.json",
        "invalid-fractional-feed.json",
    ],
)
def test_shared_invalid_fixtures_fail(name):
    with pytest.raises(JobValidationError):
        validate_job(load(name))


def test_cut_requires_opt_in_fixture_is_policy_not_schema_invalid():
    # Schema-valid cut job; default device policy still rejects without allow_cut.
    cut_job = load("cut-requires-opt-in.json")
    with pytest.raises(JobValidationError, match="allow_cut"):
        validate_job(cut_job)
    assert validate_job(cut_job, allow_cut=True)["job_id"] == "invalid-cut-gate"


@pytest.mark.parametrize(
    "value",
    [
        {"type": "raw", "bytes": "1b40"},
        {"type": "text", "text": ""},
        {"type": "text", "text": "hello\x1b@"},
        {"type": "feed", "lines": 100},
        {"type": "feed", "lines": True},
        {"type": "qr", "data": "https://example.com", "module_size": 0},
        {"type": "qr", "data": "https://example.com", "module_size": 9},
        {"type": "qr", "data": "https://example.com", "module_size": True},
        {"type": "image", "mime_type": "image/png", "data_base64": "iVBORw0KGgo="},
        {"type": "raster", "width": 8, "height": 2, "data_base64": "AA=="},
        {"type": "raster", "width": 8, "height": 1, "data_base64": "invalid"},
        {"type": "cut", "mode": "partial"},
        {"type": "text", "text": "Styled", "align": "justify"},
        {"type": "text", "text": "Styled", "align": []},
        {"type": "text", "text": "Styled", "width_multiplier": 3},
    ],
)
def test_rejects_unsafe_or_unsupported_blocks(value):
    with pytest.raises(JobValidationError):
        validate_job(job(value))


def test_rejects_boolean_feed_lines():
    with pytest.raises(JobValidationError, match="feed.lines"):
        validate_job(job({"type": "feed", "lines": True}))


def test_rejects_unsupported_top_level_fields():
    with pytest.raises(JobValidationError):
        validate_job(job({"type": "text", "text": "Hello"}, options={"copies": 1}))
    with pytest.raises(JobValidationError):
        validate_job(job({"type": "text", "text": "Hello"}, expires_at=None))


def test_cut_requires_verified_profile_opt_in():
    assert validate_job(job({"type": "cut", "mode": "partial"}), allow_cut=True)
