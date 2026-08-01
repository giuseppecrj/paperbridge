class QueueFullError(Exception):
    pass


class JobQueue:
    """Bounded in-memory queue. Persistence intentionally waits for Milestone 5."""

    def __init__(self, max_pending=20):
        self.max_pending = max_pending
        self._jobs = []

    def enqueue(self, job):
        if len(self._jobs) >= self.max_pending:
            raise QueueFullError("queue is full")
        self._jobs.append(job)

    def dequeue(self):
        return self._jobs.pop(0) if self._jobs else None

    def status(self):
        return {"pending": len(self._jobs), "capacity": self.max_pending}
