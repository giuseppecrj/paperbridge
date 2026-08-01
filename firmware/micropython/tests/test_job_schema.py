import pytest
from src.job_schema import JobValidationError, validate_job


def job(block):
    return {
        "schema_version": "1",
        "job_id": "job-1",
        "device_id": "device-1",
        "created_at": "2026-08-01T00:00:00Z",
        "expires_at": None,
        "content": {"kind": "receipt", "blocks": [block]},
        "options": {"copies": 1},
    }


def test_accepts_bounded_text_job():
    assert validate_job(job({"type": "text", "text": "Hello"}))["job_id"] == "job-1"


@pytest.mark.parametrize(
    "value",
    [
        {"type": "raw", "bytes": "1b40"},
        {"type": "text", "text": ""},
        {"type": "feed", "lines": 100},
        {"type": "cut", "mode": "partial"},
    ],
)
def test_rejects_unsafe_or_unverified_blocks(value):
    with pytest.raises(JobValidationError):
        validate_job(job(value))


def test_cut_requires_verified_profile_opt_in():
    assert validate_job(job({"type": "cut", "mode": "partial"}), allow_cut=True)
