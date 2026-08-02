class JobLedger:
    """Bounded in-memory terminal-result replay for one device boot."""

    def __init__(self, max_completed_ids=100):
        self.max_completed_ids = max_completed_ids
        self._results = {}
        self._ids = []

    def contains(self, job_id):
        return job_id in self._results

    def get(self, job_id):
        return self._results.get(job_id)

    def record(self, job_id, result):
        if job_id in self._results:
            return
        self._results[job_id] = result
        self._ids.append(job_id)
        if len(self._ids) > self.max_completed_ids:
            del self._results[self._ids.pop(0)]
