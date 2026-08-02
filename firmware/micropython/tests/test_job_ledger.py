from src.job_ledger import JobLedger


def test_ledger_tracks_completed_ids_and_evicts_the_oldest():
    ledger = JobLedger(max_completed_ids=2)

    ledger.record("job-1")
    ledger.record("job-2")
    assert ledger.contains("job-1") is True

    ledger.record("job-3")

    assert ledger.contains("job-1") is False
    assert ledger.contains("job-2") is True
    assert ledger.contains("job-3") is True


def test_fresh_ledger_forgets_completed_jobs_after_reboot():
    before_reboot = JobLedger(max_completed_ids=2)
    before_reboot.record("job-1")

    after_reboot = JobLedger(max_completed_ids=2)

    assert after_reboot.contains("job-1") is False


def test_recording_the_same_job_does_not_consume_capacity_twice():
    ledger = JobLedger(max_completed_ids=2)

    ledger.record("job-1")
    ledger.record("job-1")
    ledger.record("job-2")

    assert ledger.contains("job-1") is True
    assert ledger.contains("job-2") is True
