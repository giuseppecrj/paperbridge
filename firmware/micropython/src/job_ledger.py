class JobLedger:
    """Bounded in-memory completed-job IDs for one device boot."""

    def __init__(self, max_completed_ids=100):
        self.max_completed_ids = max_completed_ids
        self._completed = {}
        self._ids = []

    def contains(self, job_id):
        return job_id in self._completed

    def record(self, job_id):
        if job_id in self._completed:
            return
        self._completed[job_id] = True
        self._ids.append(job_id)
        if len(self._ids) > self.max_completed_ids:
            del self._completed[self._ids.pop(0)]
