from src.job_ledger import JobLedger


def test_ledger_replays_terminal_results_and_evicts_the_oldest():
    ledger = JobLedger(max_completed_ids=2)
    first = {"job_id": "job-1", "status": "delivered_to_printer"}
    second = {"job_id": "job-2", "status": "rejected"}
    third = {"job_id": "job-3", "status": "failed"}

    ledger.record("job-1", first)
    ledger.record("job-2", second)
    assert ledger.get("job-1") == first

    ledger.record("job-3", third)

    assert ledger.get("job-1") is None
    assert ledger.get("job-2") == second
    assert ledger.get("job-3") == third


def test_recording_the_same_job_keeps_the_original_terminal_result():
    ledger = JobLedger(max_completed_ids=2)
    original = {"job_id": "job-1", "status": "delivered_to_printer"}

    ledger.record("job-1", original)
    ledger.record("job-1", {"job_id": "job-1", "status": "failed"})

    assert ledger.get("job-1") == original
