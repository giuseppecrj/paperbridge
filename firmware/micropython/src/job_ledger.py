class JobLedger:
    """Bounded RAM deduplication; persistent storage is deferred to Milestone 5."""

    def __init__(self, max_completed_ids=100):
        self.max_completed_ids = max_completed_ids
        self._ids = []

    def contains(self, job_id):
        return job_id in self._ids

    def record(self, job_id):
        if job_id in self._ids:
            return
        self._ids.append(job_id)
        if len(self._ids) > self.max_completed_ids:
            self._ids.pop(0)
